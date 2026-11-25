"""N3 smoke test: run the bounded ReAct agent with a local open-weight model.

The agent only sees an anonymous RCAEvalReplay (random case id, clock-gated
telemetry). Ground truth is read from the case folder name *after* the run, by
this evaluator, and is never passed to the agent.

    # terminal 1
    mlx_lm.server --model mlx-community/Qwen3-4B-4bit --port 8080
    # terminal 2
    uv run python experiments/n3/run_smoke_test.py datasets/RCAEval/RE2-OB
"""

from __future__ import annotations

import argparse
import json
import platform
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from rca_agent.llm.react_loop import run_react
from rca_agent.llm.vllm_client import VLLMClient
from telemetry_access import RCAEvalReplay

DEFAULT_CASES = (
    "re2ob_checkoutservice_cpu_1",
    "re2ob_currencyservice_delay_1",
    "re2ob_emailservice_mem_1",
    "re2ob_productcatalogservice_loss_1",
    "re2ob_recommendationservice_disk_1",
)


def truth_of(case: Path) -> tuple[str, str]:
    _, service, fault, _ = case.name.split("_")
    return service, fault


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("case_root", type=Path)
    parser.add_argument("--cases", default=",".join(DEFAULT_CASES))
    parser.add_argument("--base-url", default="http://127.0.0.1:8080/v1")
    parser.add_argument("--model", default="mlx-community/Qwen3-4B-4bit")
    parser.add_argument("--label", default=None, help="Output sub-folder name")
    parser.add_argument("--max-tool-calls", type=int, default=12)
    parser.add_argument("--think", action="store_true", help="Allow Qwen3 thinking mode")
    parser.add_argument("--prompt", default="v2", choices=["v1", "v2"])
    parser.add_argument("--output", type=Path, default=Path("experiments/n3/trajectories"))
    args = parser.parse_args()

    try:
        served = httpx.get(f"{args.base_url}/models", timeout=10).json()
    except httpx.HTTPError as exc:
        raise SystemExit(f"No model server at {args.base_url}: {exc}") from exc
    label = args.label or f"{args.model.split('/')[-1].replace(':', '-')}_prompt-{args.prompt}"
    out_dir = args.output / label
    out_dir.mkdir(parents=True, exist_ok=True)
    llm = VLLMClient(base_url=args.base_url, model=args.model, timeout=600)

    rows = []
    for number, name in enumerate(args.cases.split(","), 1):
        case = args.case_root / name
        source = RCAEvalReplay(case)
        started = time.perf_counter()
        result = run_react(
            llm,
            source,
            case_id=source.case_id,
            max_tool_calls=args.max_tool_calls,
            no_think=not args.think,
            prompt=args.prompt,
        )
        seconds = round(time.perf_counter() - started, 1)
        service, fault = truth_of(case)
        rank = (
            result["top_services"].index(service) + 1 if service in result["top_services"] else None
        )
        result["evaluation"] = {
            "case": name,
            "true_service": service,
            "fault": fault,
            "rank_of_truth": rank,
            "seconds": seconds,
            "clock_source": source.clock_source,
        }
        (out_dir / f"case_{number:03d}.json").write_text(json.dumps(result, indent=2, default=str))
        rows.append(
            {
                "file": f"case_{number:03d}.json",
                **result["evaluation"],
                "status": result["status"],
                "top_services": result["top_services"],
                "tool_calls": result["tool_calls"],
                "invalid_tool_calls": result["invalid_tool_calls"],
                "unknown_services": result["unknown_services"],
                "unsupported_claims": result["unsupported_claims"],
                "n_claims": len(result["claims"]),
                "parse_repairs": result["parse_repairs"],
                "tools_used": [s["tool"] for s in result["steps"] if s.get("tool")],
            }
        )
        print(json.dumps(rows[-1]))

    total_calls = sum(r["tool_calls"] for r in rows)
    summary = {
        "generated_utc": datetime.now(UTC).isoformat(),
        "model": args.model,
        "served_models": [m.get("id") for m in served.get("data", [])],
        "base_url": args.base_url,
        "host": f"{platform.system()} {platform.machine()}",
        "max_tool_calls": args.max_tool_calls,
        "thinking": args.think,
        "prompt": args.prompt,
        "n_cases": len(rows),
        "completed": sum(r["status"] == "completed" for r in rows),
        "ac1": sum(r["rank_of_truth"] == 1 for r in rows) / len(rows),
        "ac3": sum(bool(r["rank_of_truth"]) and r["rank_of_truth"] <= 3 for r in rows) / len(rows),
        "tool_calls": total_calls,
        "invalid_tool_calls": sum(r["invalid_tool_calls"] for r in rows),
        "valid_tool_call_rate": (
            1 - sum(r["invalid_tool_calls"] for r in rows) / total_calls if total_calls else None
        ),
        "mean_seconds_per_case": round(sum(r["seconds"] for r in rows) / len(rows), 1),
        "cases": rows,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps({k: v for k, v in summary.items() if k != "cases"}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
