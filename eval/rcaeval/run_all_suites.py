"""Run the full RCAEval track on every downloaded suite and write a master report."""

from __future__ import annotations

import argparse
import json

from eval.rcaeval.baselines import run_baselines
from eval.rcaeval.common import ALL_SUITES, ARTIFACTS, find_data_root, list_cases, save_json
from eval.rcaeval.deep_eda import run_deep_eda
from eval.rcaeval.train_ranker import run_ranker
from eval.rcaeval.window_sweep import run_window_sweep


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suites",
        nargs="*",
        default=None,
        help="Suites to run (default: all present on disk)",
    )
    parser.add_argument("--skip-baro", action="store_true")
    parser.add_argument("--limit", type=int, default=None)
    args = parser.parse_args()

    root = find_data_root()
    suites = args.suites or [s for s in ALL_SUITES if list_cases(root, s)]
    master: dict = {"data_root": str(root), "suites": {}}

    for suite in suites:
        n = len(list_cases(root, suite))
        print(f"\n======== {suite} ({n} cases) ========")
        block: dict = {"n_cases": n}
        block["deep_eda"] = run_deep_eda(suite)
        block["window_sweep"] = run_window_sweep(suite, limit=args.limit)
        chosen = int(block["window_sweep"].get("chosen_window_sec") or 120)
        block["ranker"] = run_ranker(suite, window=chosen)
        if args.skip_baro:
            block["baro"] = {"skipped": True}
        else:
            block["baro"] = run_baselines(suite, limit=args.limit)
        master["suites"][suite] = {
            "n_cases": n,
            "chosen_window_sec": chosen,
            "ranker_AC@1": block["ranker"].get("AC@1"),
            "ranker_AC@3": block["ranker"].get("AC@3"),
            "baro_AC@1": (block["baro"].get("overall") or {}).get("AC@1"),
            "baro_AC@3": (block["baro"].get("overall") or {}).get("AC@3"),
            "baro_Avg@5": (block["baro"].get("overall") or {}).get("Avg@5"),
            "avg_metrics_cols": block["deep_eda"].get("avg_metrics_cols"),
            "avg_logs_rows": block["deep_eda"].get("avg_logs_rows"),
            "avg_traces_rows": block["deep_eda"].get("avg_traces_rows"),
        }

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    save_json(ARTIFACTS / "ALL_SUITES_SUMMARY.json", master)

    lines = [
        "# RCAEval — All Suites Results",
        "",
        f"Data root: `{root}`",
        "",
        "| Suite | Cases | Window | Ranker AC@1 | Ranker AC@3 | BARO AC@1 | BARO AC@3 | BARO Avg@5 |",
        "|------|------:|-------:|------------:|------------:|----------:|----------:|-----------:|",
    ]
    for suite, b in master["suites"].items():
        lines.append(
            f"| {suite} | {b['n_cases']} | {b['chosen_window_sec']}s | "
            f"{b['ranker_AC@1']:.3f} | {b['ranker_AC@3']:.3f} | "
            f"{(b['baro_AC@1'] if b['baro_AC@1'] is not None else float('nan')):.3f} | "
            f"{(b['baro_AC@3'] if b['baro_AC@3'] is not None else float('nan')):.3f} | "
            f"{(b['baro_Avg@5'] if b['baro_Avg@5'] is not None else float('nan')):.3f} |"
        )
    lines += [
        "",
        "## Notes",
        "- RE1 is metrics-only (no logs/traces).",
        "- RE2/RE3 include multi-source telemetry where available.",
        "- Per-suite deep data cards and JSON live under `eval/artifacts/rcaeval/`.",
        "",
        "## Reproduce",
        "```bash",
        "uv run python -m eval.rcaeval.run_all_suites",
        "```",
    ]
    (ARTIFACTS / "ALL_SUITES_RESULTS.md").write_text("\n".join(lines) + "\n")
    print("\n" + "\n".join(lines))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
