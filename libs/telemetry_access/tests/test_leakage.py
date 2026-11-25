"""Leakage tests on real RE2-OB cases.

An investigator must not be able to recover the case folder, the fault label
or the injection time from anything the replay returns, and must never see a
row stamped after ``now()``.
"""

import json
from pathlib import Path

import pytest
from telemetry_access import RCAEvalReplay

CASE_ROOT = Path(__file__).resolve().parents[3] / "datasets" / "RCAEval" / "RE2-OB"
CASES = sorted(CASE_ROOT.glob("re2ob_*_*_1"))[::6] if CASE_ROOT.is_dir() else []
FAULTS = {"cpu", "mem", "disk", "delay", "loss", "socket"}
FORBIDDEN_KEYS = {"inject_time", "label", "fault", "root_cause", "path", "case_path", "file"}

pytestmark = pytest.mark.skipif(not CASES, reason="RE2-OB replay data not available")


def _everything(source: RCAEvalReplay) -> dict:
    far_future = source.now() + 10**6
    services = source.services()
    return {
        "case_id": source.case_id,
        "now": source.now(),
        "topology": source.topology(),
        "metrics": source.metrics(None, 0, far_future, step=30),
        "logs": [row for s in services for row in source.logs(s, 0, far_future, limit=200)],
        "logs_any": source.logs(None, 0, far_future, limit=2000),
        "traces": [row for s in services for row in source.traces(s, 0, far_future, limit=200)],
    }


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_no_row_after_clock(case: Path):
    source = RCAEvalReplay(case)
    out = _everything(source)
    rows = out["logs"] + out["logs_any"] + out["traces"]
    metric_times = [ts for s in out["metrics"]["data"]["result"] for ts, _ in s["values"]]
    assert rows and metric_times, "replay returned no telemetry at all"
    assert max(row["timestamp"] for row in rows) <= source.now()
    assert max(metric_times) <= source.now()


@pytest.mark.parametrize("case", CASES, ids=lambda p: p.name)
def test_no_identity_or_label_leaks(case: Path):
    source = RCAEvalReplay(case)
    out = _everything(source)
    blob = json.dumps(out, default=str).lower()
    _, service, fault, number = case.name.split("_")
    inject_time = (case / "inject_time.txt").read_text().strip()
    # Metric names such as "<service>_cpu" are genuine telemetry, so only the
    # case-level identifiers are checked as substrings.
    needles = [case.name, str(case.resolve()), f"{service}_{fault}_{number}", "re2ob", "inject"]
    leaked = [needle for needle in needles if needle.lower() in blob]
    assert not leaked
    assert out["now"] != int(inject_time)
    metric_labels = [s["metric"] for s in out["metrics"]["data"]["result"]]
    keys = {k for row in metric_labels + out["logs"] + out["traces"] for k in row}
    assert not keys & FORBIDDEN_KEYS
    assert not FAULTS & {str(k).lower() for k in keys}
    assert out["case_id"].startswith("replay-")
    assert service not in out["case_id"]


@pytest.mark.parametrize("case", CASES[:1], ids=lambda p: p.name)
def test_case_id_is_not_derived_from_path(case: Path):
    ids = {RCAEvalReplay(case).case_id for _ in range(5)}
    assert len(ids) == 5
