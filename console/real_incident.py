"""Real RE2-OB incident path for the console: TAL replay -> LLM agent -> planner.

The UI shows a case only by an anonymous label until the operator asks to
reveal the answer; the agent itself only ever sees the RCAEvalReplay.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import httpx
from common.schema import Candidate
from telemetry_access import RCAEvalReplay

REPO_ROOT = Path(__file__).resolve().parents[1]


def _case_root() -> Path:
    roots = [REPO_ROOT / "datasets" / "RCAEval", REPO_ROOT.parent / "datasets" / "RCAEval"]
    if os.environ.get("RCAEVAL_DIR"):
        roots.insert(0, Path(os.environ["RCAEVAL_DIR"]))
    for root in roots:
        if (root / "RE2-OB").is_dir():
            return root / "RE2-OB"
    return roots[0] / "RE2-OB"


CASE_ROOT = _case_root()
TRAJECTORIES = REPO_ROOT / "experiments" / "n3" / "trajectories"
OFFICIAL = REPO_ROOT / "eval" / "artifacts" / "rcaeval" / "official_runs"
N1_RESULTS = REPO_ROOT / "eval" / "artifacts" / "rcaeval" / "n1" / "n1_results.json"
SAVED_RUN = "extended30_Qwen3-4B-4bit_prompt-v2"
_FAULT_BY_SUFFIX = {
    "cpu": "cpu",
    "mem": "mem",
    "diskio": "disk",
    "socket": "socket",
    "latency": "delay",
    "error": "unknown",
    "workload": "unknown",
}


def demo_cases() -> list[str]:
    """One case per service x fault (the 30 cases of the extended N3 run)."""
    if not CASE_ROOT.is_dir():
        return []
    return sorted(p.name for p in CASE_ROOT.iterdir() if p.name.endswith("_1"))


def truth(case: str) -> tuple[str, str]:
    _, service, fault, _ = case.split("_")
    return service, fault


def replay(case: str) -> RCAEvalReplay:
    return RCAEvalReplay(CASE_ROOT / case)


def saved_trajectory(case: str, run: str = SAVED_RUN) -> dict | None:
    folder = TRAJECTORIES / run
    for path in sorted(folder.glob("case_*.json")):
        data = json.loads(path.read_text())
        if data.get("evaluation", {}).get("case") == case:
            return data
    return None


def server_model(base_url: str) -> str | None:
    try:
        models = httpx.get(f"{base_url}/models", timeout=2).json().get("data", [])
    except (httpx.HTTPError, ValueError):
        return None
    return models[0]["id"] if models else None


def run_live(case: str, base_url: str, model: str, prompt: str = "v2") -> dict:
    from rca_agent.llm.react_loop import run_react
    from rca_agent.llm.vllm_client import VLLMClient

    source = replay(case)
    llm = VLLMClient(base_url=base_url, model=model, timeout=300)
    return run_react(llm, source, case_id=source.case_id, prompt=prompt)


def _metric_tables(trajectory: dict) -> list[dict]:
    rows = []
    for message in trajectory.get("messages", []):
        if message.get("role") != "tool" or message.get("name") != "get_metrics":
            continue
        try:
            rows.extend(json.loads(message["content"]).get("metrics", []))
        except (json.JSONDecodeError, TypeError):
            continue
    return rows


RESOURCE_FAULTS = ("cpu", "mem", "disk", "socket")
RESOURCE_Z = 3.0


def classify_fault(
    rows: list[dict], service: str, rule: str = "resource_first"
) -> tuple[str, str | None]:
    """Fault family from a service's metric changes.

    ``max``: family of the most-changed metric. ``resource_first``: latency rises under
    every fault, so a resource metric (cpu/mem/disk/socket) beyond RESOURCE_Z wins over it.
    """
    scored = []
    for row in rows:
        metric = str(row.get("metric", ""))
        if not metric.startswith(f"{service}_"):
            continue
        suffix = metric[len(service) + 1 :].split("-")[0]
        scored.append(
            (abs(row.get("z_score") or 0), _FAULT_BY_SUFFIX.get(suffix, "unknown"), metric)
        )
    if not scored:
        return "unknown", None
    if rule == "resource_first":
        resource = [s for s in scored if s[1] in RESOURCE_FAULTS and s[0] >= RESOURCE_Z]
        if resource:
            scored = resource
    _, family, metric = max(scored)
    return family, metric


def fault_hint(
    trajectory: dict, service: str, rule: str = "resource_first"
) -> tuple[str, str | None]:
    """Fault family suggested by the service's metric changes in the agent's evidence."""
    return classify_fault(_metric_tables(trajectory), service, rule)


def candidates(trajectory: dict) -> list[Candidate]:
    """Agent ranking as planner candidates. Confidence is rank-based, not calibrated."""
    tops = trajectory.get("top_services") or []
    cited = {c.get("service"): c.get("evidence_refs", []) for c in trajectory.get("claims", [])}
    return [
        Candidate(
            service=service,
            score=1.0 / rank,
            rank=rank,
            evidence=list(cited.get(service, [])),
            confidence=round(1.0 / rank, 2),
            uncertainty="rank-based placeholder; calibrated sets come in Phase 1",
        )
        for rank, service in enumerate(tops, 1)
    ]


BASELINE_LABELS = {"nsigma": "N-Sigma", "circa": "CIRCA", "rcd": "RCD", "baro": "BARO"}


def baseline_rankings(case: str, methods: tuple[str, ...] = tuple(BASELINE_LABELS)) -> dict:
    _, service, fault, number = case.split("_")
    out = {}
    for method in methods:
        path = OFFICIAL / method / "results" / f"{service}_{fault}_{number}.json"
        if not path.exists():
            continue
        services: list[str] = []
        for metric in json.loads(path.read_text())["0"]:
            name = metric.split("_")[0]
            if name not in services:
                services.append(name)
        out[BASELINE_LABELS.get(method, method)] = services[:5]
    return out


def run_summaries() -> list[dict]:
    rows = []
    for path in sorted(TRAJECTORIES.glob("*/summary.json")):
        summary = json.loads(path.read_text())
        rows.append(
            {
                "run": path.parent.name,
                **{k: v for k, v in summary.items() if k != "cases"},
                "cases": summary["cases"],
            }
        )
    return rows


def n1_results() -> dict | None:
    return json.loads(N1_RESULTS.read_text()) if N1_RESULTS.exists() else None
