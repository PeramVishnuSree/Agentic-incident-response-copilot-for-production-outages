"""Run BARO baseline on RCAEval cases and score AC@k / Avg@5."""

from __future__ import annotations

from collections import defaultdict

from tqdm import tqdm

from eval.rcaeval.common import (
    ARTIFACTS,
    ac_at_k,
    avg_at_5,
    find_data_root,
    inject_time,
    list_cases,
    load_metrics,
    ranks_to_services,
    save_json,
)


def run_baro_case(case) -> dict:
    from RCAEval.e2e import baro

    data = load_metrics(case)
    # Drop constant columns for stability
    keep = ["time"]
    for c in data.columns:
        if c == "time":
            continue
        if data[c].nunique(dropna=True) > 1:
            keep.append(c)
    data = data[keep]
    out = baro(data, inject_time(case))
    ranks = list(out["ranks"])
    services = ranks_to_services(ranks)
    truth = case.service
    return {
        "case": case.name,
        "truth": truth,
        "fault": case.fault,
        "top_metrics": ranks[:10],
        "top_services": services[:10],
        "ac1": ac_at_k(services, truth, 1),
        "ac3": ac_at_k(services, truth, 3),
        "ac5": ac_at_k(services, truth, 5),
        "avg5": avg_at_5(services, truth),
    }


def run_baselines(suite: str = "re2ob", limit: int | None = None) -> dict:
    root = find_data_root()
    cases = list_cases(root, suite=suite)
    if limit:
        cases = cases[:limit]

    rows = []
    for case in tqdm(cases, desc=f"BARO {suite}"):
        try:
            rows.append(run_baro_case(case))
        except Exception as exc:  # noqa: BLE001
            rows.append(
                {
                    "case": case.name,
                    "truth": case.service,
                    "fault": case.fault,
                    "error": str(exc),
                    "ac1": 0.0,
                    "ac3": 0.0,
                    "ac5": 0.0,
                    "avg5": 0.0,
                }
            )

    by_fault: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for k in ("ac1", "ac3", "ac5", "avg5"):
            by_fault[r["fault"]][k].append(float(r[k]))

    summary = {
        "method": "BARO",
        "suite": suite,
        "n_cases": len(rows),
        "n_errors": sum(1 for r in rows if "error" in r),
        "overall": {
            "AC@1": sum(r["ac1"] for r in rows) / max(len(rows), 1),
            "AC@3": sum(r["ac3"] for r in rows) / max(len(rows), 1),
            "AC@5": sum(r["ac5"] for r in rows) / max(len(rows), 1),
            "Avg@5": sum(r["avg5"] for r in rows) / max(len(rows), 1),
        },
        "by_fault": {
            fault: {k: sum(vals) / len(vals) for k, vals in metrics.items()}
            for fault, metrics in by_fault.items()
        },
    }

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    save_json(ARTIFACTS / f"{suite}_baro_cases.json", rows)
    save_json(ARTIFACTS / f"{suite}_baro_summary.json", summary)
    return summary


if __name__ == "__main__":
    import json
    import sys

    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print(json.dumps(run_baselines("re2ob", limit=lim), indent=2))
