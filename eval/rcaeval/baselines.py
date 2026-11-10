"""Run RCAEval metric baselines (BARO, N-Sigma, E-Diagnosis) and score AC@k / Avg@5."""

from __future__ import annotations

from collections import defaultdict
from typing import Callable

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

# Metric-only methods that work on RE2-OB parquet without extra graph/log inputs.
DEFAULT_METHODS = ("baro", "nsigma", "e_diagnosis")


def _prepare_metrics(case):
    data = load_metrics(case)
    keep = ["time"]
    for c in data.columns:
        if c == "time":
            continue
        if data[c].nunique(dropna=True) > 1:
            keep.append(c)
    return data[keep]


def _resolve_method(name: str) -> Callable:
    from RCAEval import e2e

    fn = getattr(e2e, name, None)
    if fn is None or not callable(fn):
        raise ValueError(f"Unknown RCAEval e2e method: {name}")
    return fn


def run_method_case(case, method: str) -> dict:
    fn = _resolve_method(method)
    data = _prepare_metrics(case)
    out = fn(data, inject_time(case))
    ranks = list(out["ranks"])
    services = ranks_to_services(ranks)
    truth = case.service
    return {
        "case": case.name,
        "truth": truth,
        "fault": case.fault,
        "method": method,
        "top_metrics": ranks[:10],
        "top_services": services[:10],
        "ac1": ac_at_k(services, truth, 1),
        "ac3": ac_at_k(services, truth, 3),
        "ac5": ac_at_k(services, truth, 5),
        "avg5": avg_at_5(services, truth),
    }


def run_baro_case(case) -> dict:
    """Back-compat wrapper used by older scripts."""
    row = run_method_case(case, "baro")
    row.pop("method", None)
    return row


def _summarize(rows: list[dict], method: str, suite: str) -> dict:
    by_fault: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
    for r in rows:
        for k in ("ac1", "ac3", "ac5", "avg5"):
            by_fault[r["fault"]][k].append(float(r[k]))

    return {
        "method": method,
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
            for fault, metrics in sorted(by_fault.items())
        },
    }


def run_baselines(
    suite: str = "re2ob",
    limit: int | None = None,
    methods: tuple[str, ...] | list[str] | None = None,
) -> dict:
    """Run one or more metric baselines. Default keeps BARO-only for back-compat callers."""
    root = find_data_root()
    cases = list_cases(root, suite=suite)
    if limit:
        cases = cases[:limit]

    selected = tuple(methods) if methods else ("baro",)
    combined: dict = {"suite": suite, "methods": {}}

    for method in selected:
        rows = []
        for case in tqdm(cases, desc=f"{method} {suite}"):
            try:
                rows.append(run_method_case(case, method))
            except Exception as exc:  # noqa: BLE001
                rows.append(
                    {
                        "case": case.name,
                        "truth": case.service,
                        "fault": case.fault,
                        "method": method,
                        "error": str(exc),
                        "ac1": 0.0,
                        "ac3": 0.0,
                        "ac5": 0.0,
                        "avg5": 0.0,
                    }
                )

        summary = _summarize(rows, method=method, suite=suite)
        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        save_json(ARTIFACTS / f"{suite}_{method}_cases.json", rows)
        save_json(ARTIFACTS / f"{suite}_{method}_summary.json", summary)
        # Preserve historical BARO filenames.
        if method == "baro":
            save_json(ARTIFACTS / f"{suite}_baro_cases.json", rows)
            save_json(ARTIFACTS / f"{suite}_baro_summary.json", summary)
        combined["methods"][method] = summary

    # Back-compat: if only BARO was requested, return the BARO summary object.
    if selected == ("baro",):
        return combined["methods"]["baro"]
    return combined


if __name__ == "__main__":
    import json
    import sys

    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print(json.dumps(run_baselines("re2ob", limit=lim, methods=DEFAULT_METHODS), indent=2))
