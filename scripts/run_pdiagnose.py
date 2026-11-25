"""PDiagnose on every RE2-OB case, ported from RCAEval's one-case demo.

Upstream ``RCAEval/e2e/pdiagnose.py`` (commit 3c3e25f) is a ``main()`` with a
hard-coded case path and is not wired into ``main.py``. This script applies the
same scoring to each case without changing it:

* metrics: per column, count anomalous-period samples >= mean + 3*std of the
  normal period; add ALPHA * count to the column's service;
* logs: count lines containing ``error|fail`` (case-sensitive, whole case) per
  container; add ALPHA * count;
* traces: per operation, flag spans whose duration exceeds the normal-period
  mean + 3*std; add ALPHA * abnormal spans to the span's service.

Results are written in ``main.py``'s layout (``results/<service>_<fault>_<n>.json``)
so they are scored exactly like the official methods.

    uv run python scripts/run_pdiagnose.py --data-root ../external/RCAEval/data/RE2/RE2-OB
"""

from __future__ import annotations

import argparse
import json
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pandas as pd

ALPHA = 5


def rank_case(case_dir: Path) -> list[str]:
    metric_df = pd.read_csv(case_dir / "simple_metrics.csv")
    log_df = pd.read_csv(case_dir / "logs.csv", usecols=["container_name", "message"])
    span_df = pd.read_csv(
        case_dir / "traces.csv",
        usecols=["serviceName", "methodName", "operationName", "startTime", "duration"],
    )
    inject_time = int((case_dir / "inject_time.txt").read_text().split()[0])

    normal = metric_df[metric_df["time"] < inject_time]
    anomal = metric_df[metric_df["time"] >= inject_time]
    columns = [c for c in metric_df.columns if "time" not in c]
    services: dict[str, float] = {c.split("_")[0]: 0.0 for c in columns}
    for column in columns:
        limit = normal[column].mean() + 3 * normal[column].std()
        services[column.split("_")[0]] += ALPHA * int((anomal[column] >= limit).sum())

    errors = log_df["message"].astype(str).str.contains("error|fail")
    for container, count in log_df.loc[errors, "container_name"].value_counts().items():
        services[container] = services.get(container, 0.0) + ALPHA * int(count)

    span_df["methodName"] = span_df["methodName"].fillna(span_df["operationName"])
    span_df["operation"] = span_df["serviceName"] + "_" + span_df["methodName"]
    end = span_df["startTime"] + span_df["duration"]
    inject_us = inject_time * 1_000_000
    normal_spans = span_df[end < inject_us]
    anomal_spans = span_df[end >= inject_us].copy()
    slo = normal_spans.groupby("operation")["duration"].agg(["mean", "std"]) / 1_000
    anomal_spans = anomal_spans.join(slo, on="operation")
    anomal_spans["abnormal"] = (
        anomal_spans["duration"] / 1_000 >= anomal_spans["mean"] + 3 * anomal_spans["std"]
    )
    for service, abnormal in anomal_spans.groupby("serviceName")["abnormal"].sum().items():
        name = "frontend" if service == "frontendservice" else service
        services[name] = services.get(name, 0.0) + ALPHA * int(abnormal)

    return [s for s, _ in sorted(services.items(), key=lambda item: item[1], reverse=True)]


def _run(case_dir: Path) -> tuple[str, list[str]]:
    service, fault = case_dir.parent.name.rsplit("_", 1)
    return f"{service}_{fault}_{case_dir.name}", rank_case(case_dir)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, required=True, help="…/data/RE2/RE2-OB")
    parser.add_argument(
        "--output", type=Path, default=Path("eval/artifacts/rcaeval/official_runs/pdiagnose")
    )
    parser.add_argument("--workers", type=int, default=6)
    args = parser.parse_args()
    cases = sorted(p for p in args.data_root.glob("*_*/*") if (p / "simple_metrics.csv").exists())
    if not cases:
        raise SystemExit(f"No RE2-OB cases under {args.data_root}")
    results = args.output / "results"
    results.mkdir(parents=True, exist_ok=True)
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        for case_id, ranks in pool.map(_run, cases):
            (results / f"{case_id}.json").write_text(json.dumps({"0": ranks}))
    (args.output / "run.json").write_text(
        json.dumps(
            {
                "method": "pdiagnose",
                "dataset": "re2-ob",
                "command": "scripts/run_pdiagnose.py (port of RCAEval/e2e/pdiagnose.py main())",
                "upstream_wired_into_main_py": False,
                "returncode": 0,
                "n_case_results": len(cases),
            },
            indent=2,
        )
    )
    print(f"Wrote {len(cases)} PDiagnose rankings to {results}")


if __name__ == "__main__":
    main()
