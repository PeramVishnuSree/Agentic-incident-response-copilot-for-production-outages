"""Deep EDA for RCAEval RE2 (metrics / logs / traces)."""

from __future__ import annotations

from collections import Counter, defaultdict

import numpy as np
import pandas as pd

from eval.rcaeval.common import (
    ARTIFACTS,
    find_data_root,
    inject_time,
    list_cases,
    load_logs,
    load_metrics,
    load_traces,
    metric_to_service,
    save_json,
)


def _missing_rate(df: pd.DataFrame) -> float:
    if df.empty:
        return 0.0
    return float(df.isna().mean().mean())


def _constant_cols(df: pd.DataFrame) -> list[str]:
    cols = []
    for c in df.columns:
        if c == "time":
            continue
        s = df[c]
        if s.nunique(dropna=True) <= 1:
            cols.append(c)
    return cols


def _sampling_interval(times: pd.Series) -> float | None:
    if len(times) < 3:
        return None
    diffs = np.diff(sorted(times.dropna().astype(float).tolist()))
    diffs = diffs[diffs > 0]
    return float(np.median(diffs)) if len(diffs) else None


def analyze_case(case) -> dict:
    metrics = load_metrics(case)
    logs = load_logs(case)
    traces = load_traces(case)
    t0 = inject_time(case)

    metric_cols = [c for c in metrics.columns if c != "time"]
    pre = metrics[metrics["time"] < t0]
    post = metrics[metrics["time"] >= t0]

    # Pre/post mean shift for root-cause service columns
    truth_cols = [c for c in metric_cols if metric_to_service(c) == case.service]
    shifts = {}
    for c in truth_cols[:12]:
        if len(pre) and len(post) and pre[c].std() > 0:
            shifts[c] = float((post[c].mean() - pre[c].mean()) / (pre[c].std() + 1e-9))

    log_error_rate = None
    if not logs.empty and "message" in logs.columns:
        msgs = logs["message"].astype(str).str.lower()
        err = msgs.str.contains("error|fail|exception|timeout|unavailable", regex=True)
        log_error_rate = float(err.mean())

    trace_err = None
    if not traces.empty and "statusCode" in traces.columns:
        trace_err = float((traces["statusCode"].fillna(0) != 0).mean())

    services_in_metrics = sorted(
        {metric_to_service(c) for c in metric_cols if metric_to_service(c)}
    )

    return {
        "case": case.name,
        "service": case.service,
        "fault": case.fault,
        "inject_time": t0,
        "metrics_rows": int(len(metrics)),
        "metrics_cols": int(len(metric_cols)),
        "metric_missing_rate": _missing_rate(metrics[metric_cols]) if metric_cols else 0.0,
        "constant_metric_cols": len(_constant_cols(metrics)),
        "sampling_interval_sec": _sampling_interval(metrics["time"]),
        "pre_rows": int(len(pre)),
        "post_rows": int(len(post)),
        "truth_metric_shift_z": shifts,
        "max_abs_truth_shift_z": max((abs(v) for v in shifts.values()), default=0.0),
        "logs_rows": int(len(logs)),
        "log_error_rate": log_error_rate,
        "traces_rows": int(len(traces)),
        "trace_error_rate": trace_err,
        "services_in_metrics": services_in_metrics,
        "leakage_folder_encodes_label": True,
    }


def run_deep_eda(suite: str = "re2ob") -> dict:
    root = find_data_root()
    cases = list_cases(root, suite=suite)
    rows = [analyze_case(c) for c in cases]
    df = pd.DataFrame(rows)

    by_fault = (
        df.groupby("fault")
        .agg(
            n=("case", "count"),
            median_metrics_cols=("metrics_cols", "median"),
            median_logs=("logs_rows", "median"),
            median_traces=("traces_rows", "median"),
            mean_truth_shift=("max_abs_truth_shift_z", "mean"),
            mean_log_err=("log_error_rate", "mean"),
        )
        .reset_index()
        .to_dict(orient="records")
    )

    summary = {
        "suite": suite,
        "data_root": str(root),
        "n_cases": len(cases),
        "fault_counts": dict(Counter(df["fault"])),
        "service_counts": dict(Counter(df["service"])),
        "avg_metrics_cols": float(df["metrics_cols"].mean()),
        "avg_sampling_interval_sec": float(df["sampling_interval_sec"].dropna().mean()),
        "avg_metric_missing_rate": float(df["metric_missing_rate"].mean()),
        "avg_constant_metric_cols": float(df["constant_metric_cols"].mean()),
        "avg_logs_rows": float(df["logs_rows"].mean()),
        "avg_traces_rows": float(df["traces_rows"].mean()),
        "avg_max_abs_truth_shift_z": float(df["max_abs_truth_shift_z"].mean()),
        "by_fault": by_fault,
        "cleaning_rules": [
            "Drop constant / near-constant metric columns before ranking.",
            "Align all analysis to inject_time; use pre-window as baseline.",
            "Never put case folder names in model prompts (label leakage).",
            "Map metrics to services via known Online Boutique prefixes.",
            "Treat redis_* metrics as redis-cart in our dependency graph.",
        ],
    }

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    save_json(ARTIFACTS / f"{suite}_deep_eda_cases.json", rows)
    save_json(ARTIFACTS / f"{suite}_deep_eda_summary.json", summary)
    df.to_csv(ARTIFACTS / f"{suite}_deep_eda_cases.csv", index=False)

    card = f"""# RCAEval {suite.upper()} — Deep Data Card

## Dataset
- Root: `{root}`
- Cases: **{summary["n_cases"]}**
- Faults: `{summary["fault_counts"]}`
- Services: `{summary["service_counts"]}`

## Telemetry profile
- Avg metric columns / case: **{summary["avg_metrics_cols"]:.1f}**
- Avg sampling interval: **{summary["avg_sampling_interval_sec"]:.2f}s**
- Avg missing rate: **{summary["avg_metric_missing_rate"]:.4f}**
- Avg constant metric columns: **{summary["avg_constant_metric_cols"]:.1f}**
- Avg log lines: **{summary["avg_logs_rows"]:.0f}**
- Avg traces: **{summary["avg_traces_rows"]:.0f}**
- Mean |z| shift on true-service metrics (pre→post): **{summary["avg_max_abs_truth_shift_z"]:.2f}**

## Cleaning decisions
{chr(10).join("- " + r for r in summary["cleaning_rules"])}

## Per-fault summary
See `{suite}_deep_eda_summary.json` → `by_fault`.

## Leakage
Case directory names encode root-cause service + fault. Use only as labels.
"""
    (ARTIFACTS / f"{suite}_deep_data_card.md").write_text(card)
    return summary


if __name__ == "__main__":
    import json

    print(json.dumps(run_deep_eda("re2ob"), indent=2))
