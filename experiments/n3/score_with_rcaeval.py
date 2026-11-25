"""Score N3 agent runs with RCAEval's own predictions evaluator.

Maps our case folders (re2ob_<service>_<fault>_<n>) to the anonymised ids of
``rcaeval-agent export`` through the answers file, writes a predictions JSONL
and then runs ``rcaeval-agent evaluate``.

    uv run python experiments/n3/score_with_rcaeval.py \
        experiments/n3/trajectories/extended30_Qwen3-4B-4bit_prompt-v2 \
        --tasks ../external/RCAEval/agent_tasks/re2-ob \
        --rcaeval-agent ../external/RCAEval/env/bin/rcaeval-agent
"""

from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("run_dir", type=Path)
    parser.add_argument("--tasks", type=Path, required=True)
    parser.add_argument("--rcaeval-agent", default="rcaeval-agent")
    args = parser.parse_args()

    answers_path = args.tasks.parent / f"{args.tasks.name}.answers.jsonl"
    answers = [json.loads(line) for line in answers_path.read_text().splitlines() if line]
    by_source = {}
    for answer in answers:
        _, _, group, number = answer["source"].split("/")
        by_source[f"re2ob_{group}_{number}"] = answer

    summary = json.loads((args.run_dir / "summary.json").read_text())
    out = args.run_dir / "rcaeval_official"
    out.mkdir(exist_ok=True)
    preds, subset = [], []
    for case in summary["cases"]:
        answer = by_source[case["case"]]
        trajectory = json.loads((args.run_dir / case["file"]).read_text())
        ranks = ["redis" if s == "redis-cart" else s for s in case["top_services"]]
        preds.append(
            {
                "case_id": answer["case_id"],
                "ranks": ranks,
                "model": summary["model"],
                "reasoning": json.dumps(trajectory.get("claims", []))[:2000],
                "usage": {
                    "wall_time_s": case["seconds"],
                    "tool_calls": case["tool_calls"],
                    "input_tokens": sum(s.get("prompt_tokens") or 0 for s in trajectory["steps"]),
                    "output_tokens": sum(
                        s.get("completion_tokens") or 0 for s in trajectory["steps"]
                    ),
                },
            }
        )
        subset.append(answer)
    (out / "preds.jsonl").write_text("".join(json.dumps(p) + "\n" for p in preds))
    command = [
        args.rcaeval_agent,
        "evaluate",
        "--tasks",
        str(args.tasks),
        "--predictions",
        str(out / "preds.jsonl"),
        "--report-chance",
        "--json-out",
        str(out / "summary.json"),
        "--per-case-out",
        str(out / "per_case.jsonl"),
    ]
    proc = subprocess.run(command, text=True, capture_output=True, check=False)
    (out / "evaluate_stdout.txt").write_text(proc.stdout + proc.stderr)
    print(proc.stdout, proc.stderr)
    if proc.returncode:
        return proc.returncode
    predicted = {a["case_id"] for a in subset}
    rows = [json.loads(line) for line in (out / "per_case.jsonl").read_text().splitlines()]
    rows = [r for r in rows if r["case_id"] in predicted]
    ranks = [r.get("service_rank") for r in rows]
    covered = {
        "n_cases": len(rows),
        "AC@1": sum(r == 1 for r in ranks) / len(rows),
        "AC@3": sum(r is not None and r <= 3 for r in ranks) / len(rows),
        "AC@5": sum(r is not None and r <= 5 for r in ranks) / len(rows),
        "Avg@5": sum(sum(r is not None and r <= k for k in range(1, 6)) / 5 for r in ranks)
        / len(rows),
    }
    (out / "covered_cases_summary.json").write_text(json.dumps(covered, indent=2))
    print("Predicted cases only:", json.dumps(covered))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
