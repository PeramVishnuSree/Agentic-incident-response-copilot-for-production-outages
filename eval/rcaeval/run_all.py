"""Run the full RCAEval track: deep EDA → window sweep → ranker → BARO baselines."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eval.rcaeval.baselines import run_baselines
from eval.rcaeval.common import ARTIFACTS, save_json
from eval.rcaeval.deep_eda import run_deep_eda
from eval.rcaeval.train_ranker import run_ranker
from eval.rcaeval.window_sweep import run_window_sweep


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="re2ob")
    parser.add_argument("--limit", type=int, default=None, help="Optional case cap for smoke runs")
    parser.add_argument("--skip-baro", action="store_true", help="Skip slow BARO loop")
    args = parser.parse_args()

    report: dict = {"suite": args.suite}

    print("== Deep EDA ==")
    report["deep_eda"] = run_deep_eda(args.suite)

    print("== Window sweep ==")
    report["window_sweep"] = run_window_sweep(args.suite, limit=args.limit)

    chosen = report["window_sweep"].get("chosen_window_sec") or 300
    print(f"== Ranker (window={chosen}s) ==")
    report["ranker"] = run_ranker(args.suite, window=int(chosen))

    if not args.skip_baro:
        print("== BARO baselines ==")
        report["baro"] = run_baselines(args.suite, limit=args.limit)
    else:
        report["baro"] = {"skipped": True}

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    save_json(ARTIFACTS / f"{args.suite}_full_report.json", report)

    md = Path(ARTIFACTS / f"{args.suite}_RESULTS.md")
    baro = report.get("baro", {})
    overall = baro.get("overall", {})
    md.write_text(
        f"""# RCAEval {args.suite.upper()} — Results

## Deep EDA
- Cases: {report["deep_eda"].get("n_cases")}
- Avg metric cols: {report["deep_eda"].get("avg_metrics_cols")}
- Avg sampling interval: {report["deep_eda"].get("avg_sampling_interval_sec")} s
- Data card: `{args.suite}_deep_data_card.md`

## Window sweep
- Chosen window: **{report["window_sweep"].get("chosen_window_sec")} s**
- Reason: {report["window_sweep"].get("reason")}
- Curve: `{json.dumps(report["window_sweep"].get("results"), indent=2)}`

## Learned ranker
- Model: {report["ranker"].get("model")}
- AC@1: **{report["ranker"].get("AC@1"):.3f}**
- AC@3: **{report["ranker"].get("AC@3"):.3f}**
- Importances: `{report["ranker"].get("feature_importance")}`

## BARO baseline
- AC@1: **{overall.get("AC@1", "n/a")}**
- AC@3: **{overall.get("AC@3", "n/a")}**
- Avg@5: **{overall.get("Avg@5", "n/a")}**
- Per-fault: see `{args.suite}_baro_summary.json`

## How this answers the professor
1. **AI/ML?** BARO = statistical anomaly RCA; GBT = learned ranker; LLM agent is separate.
2. **EDA?** Deep data card + case CSV written under `eval/artifacts/rcaeval/`.
3. **Metrics validated?** Targets should be set relative to BARO AC@k on this suite.
4. **Window size?** Chosen from labelled sweep above.
"""
    )
    print(f"Wrote {md}")
    print(json.dumps({k: (v if k == "suite" else "ok") for k, v in report.items()}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
