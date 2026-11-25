from pathlib import Path

import pandas as pd
import pytest
from telemetry_access import RCAEvalReplay
from telemetry_access.replay import to_epoch_seconds

B = 1_700_000_000


def make_case(tmp_path: Path) -> Path:
    case = tmp_path / "re2ob_checkoutservice_cpu_1"
    case.mkdir()
    (case / "inject_time.txt").write_text(str(B + 100))
    pd.DataFrame(
        {
            "time": [B + 90, B + 100, B + 110, B + 120],
            "checkoutservice_cpu": [1, 2, 3, 4],
            "frontend_cpu": [5, 5, 5, 5],
            "redis_mem": [7, 7, 7, 7],
        }
    ).to_parquet(case / "metrics.parquet")
    pd.DataFrame(
        {
            "timestamp": [B + 95, B + 100, B + 110],
            "container_name": ["checkoutservice", "frontend", "checkoutservice"],
            "message": ["payment ERROR", "ok", "late error"],
        }
    ).to_parquet(case / "logs.parquet")
    pd.DataFrame(
        {
            "time": ["00:01", "00:01", "00:02"],
            "spanID": ["a", "b", "c"],
            "parentSpanID": [None, "a", "a"],
            "serviceName": ["frontendservice", "checkoutservice", "paymentservice"],
            "startTimeMillis": [(B + t) * 1000 for t in (95, 96, 115)],
            "duration": [10, 5, 3],
        }
    ).to_parquet(case / "traces.parquet")
    return case


def test_replay_clips_future_data(tmp_path: Path):
    source = RCAEvalReplay(make_case(tmp_path), now_timestamp=B + 105)
    result = source.metrics("checkoutservice", B + 90, B + 999)["data"]
    assert source.now() == B + 105
    assert result["resultType"] == "matrix"
    [series] = result["result"]
    assert series["metric"]["__name__"] == "checkoutservice_cpu"
    assert series["values"] == [[B + 90, "1"], [B + 100, "2"]]


def test_logs_use_container_name_and_pattern(tmp_path: Path):
    source = RCAEvalReplay(make_case(tmp_path), now_timestamp=B + 105)
    rows = source.logs("checkoutservice", 0, B + 999, pattern="error")
    assert [r["message"] for r in rows] == ["payment ERROR"]
    assert rows[0]["service"] == "checkoutservice"


def test_traces_use_epoch_columns_and_canonical_services(tmp_path: Path):
    source = RCAEvalReplay(make_case(tmp_path), now_timestamp=B + 105)
    rows = source.traces("frontend", 0, B + 999)
    assert [r["timestamp"] for r in rows] == [B + 95]
    assert rows[0]["service"] == "frontend"


def test_topology_comes_from_pre_clock_traces(tmp_path: Path):
    source = RCAEvalReplay(make_case(tmp_path), now_timestamp=B + 105)
    topology = source.topology()
    assert topology["edges"] == [{"caller": "frontend", "callee": "checkoutservice", "calls": 1}]
    assert "redis-cart" in topology["services"]
    assert "paymentservice" not in str(topology["edges"])


def test_topology_falls_back_to_static_graph(tmp_path: Path):
    case = tmp_path / "case"
    case.mkdir()
    pd.DataFrame({"time": [1], "a_cpu": [1.0]}).to_csv(case / "metrics.csv", index=False)
    static = {"services": ["a", "b"], "edges": [{"caller": "a", "callee": "b"}]}
    source = RCAEvalReplay(case, now_timestamp=5, topology=static)
    assert source.topology()["edges"] == [{"caller": "a", "callee": "b"}]


def test_case_ids_are_random_and_clock_source_is_recorded(tmp_path: Path):
    case = make_case(tmp_path)
    first, second = RCAEvalReplay(case), RCAEvalReplay(case)
    assert first.case_id != second.case_id
    assert first.clock_source == "oracle_inject_time_plus_300s"
    detected = RCAEvalReplay(case, onset_detector=lambda metrics: int(metrics["time"].iloc[1]))
    assert (detected.now(), detected.clock_source) == (B + 100, "onset_detector")


@pytest.mark.parametrize(
    "values",
    [
        [1_700_000_000, 1_700_000_001],
        [1_700_000_000_000, 1_700_000_001_000],
        [1_700_000_000_000_000, 1_700_000_001_000_000],
        [1_700_000_000_000_000_000, 1_700_000_001_000_000_000],
    ],
)
def test_timestamps_normalise_to_seconds(values):
    assert to_epoch_seconds(pd.Series(values)).tolist() == [1_700_000_000, 1_700_000_001]


def test_clock_like_strings_are_not_mistaken_for_dates():
    assert to_epoch_seconds(pd.Series(["03:56", "03:57"])).isna().all()
