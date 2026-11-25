"""Incident Copilot web prototype (CMPE 295A).

A real RE2-OB incident is replayed through the read-only Telemetry Access Layer,
investigated by a local LLM agent, mapped to a playbook remedy, approved by a
human, executed by the allowlisted executor in dry-run mode, and verified, with
the failed-remedy feedback loop.

Run:  make web            (http://127.0.0.1:8090)
LLM:  mlx_lm.server --model mlx-community/Qwen3-4B-4bit --port 8080   (optional)
"""

from __future__ import annotations

import json
import os
import secrets
import threading
import time
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from approval_service import ApprovalGate
from common.schema import ApprovalDecision, Candidate, RemediationPlan
from executor import AllowlistedExecutor
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from rca_agent.tools.telemetry import dispatch
from remediation_planner import draft_plan, next_plan_after_failure
from telemetry_access.replay import service_from_metric

from console import real_incident as ri

WEB = Path(__file__).resolve().parent / "web"
FIGURES = ri.REPO_ROOT / "docs" / "figures"
FAILURE_MODES = ri.REPO_ROOT / "experiments" / "n3" / "FAILURE_MODES.md"
PLANNER_EVAL = ri.REPO_ROOT / "eval" / "artifacts" / "rcaeval" / "planner" / "planner_eval.json"
LLM_URL = os.environ.get("COPILOT_LLM_URL", "http://127.0.0.1:8080/v1")
LOG_PATTERN = "error|fail|timeout|exception"
CHART_SECONDS = 1200
SAVED_STEP_DELAY = 0.9

app = FastAPI(title="Incident Copilot · 295A prototype")
app.mount("/static", StaticFiles(directory=WEB), name="static")


@app.middleware("http")
async def no_cache_static(request, call_next):
    response = await call_next(request)
    if request.url.path == "/" or request.url.path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache"
    return response


if FIGURES.is_dir():
    app.mount("/figures", StaticFiles(directory=FIGURES), name="figures")


@dataclass
class Session:
    id: str
    index: int
    case: str
    source: Any
    opened: dict
    status: str = "detected"
    agent: dict = field(
        default_factory=lambda: {
            "status": "idle",
            "mode": None,
            "model": None,
            "steps": [],
            "evidence": {},
            "error": None,
            "started": None,
            "seconds": None,
        }
    )
    trajectory: dict | None = None
    candidates: list[Candidate] = field(default_factory=list)
    fault: str = "unknown"
    fault_metric: str | None = None
    gate: ApprovalGate = field(default_factory=ApprovalGate)
    executor: AllowlistedExecutor = field(default_factory=lambda: AllowlistedExecutor(dry_run=True))
    plans: list[RemediationPlan] = field(default_factory=list)
    attempts: list[dict] = field(default_factory=list)
    failed_services: list[str] = field(default_factory=list)
    audit: list[dict] = field(default_factory=list)
    revealed: dict | None = None
    lock: threading.Lock = field(default_factory=threading.Lock)

    def log(self, actor: str, kind: str, text: str) -> None:
        self.audit.append(
            {"at": datetime.now(UTC).isoformat(), "actor": actor, "kind": kind, "text": text}
        )


SESSIONS: dict[str, Session] = {}


class InvestigateRequest(BaseModel):
    mode: str = "live"


class DecisionRequest(BaseModel):
    decision: str
    operator: str
    note: str = ""


class VerifyRequest(BaseModel):
    outcome: str = "simulate"
    operator: str = "operator"


def _incident_label(index: int) -> str:
    return f"INC-{2401 + index}"


def _session(sid: str) -> Session:
    if sid not in SESSIONS:
        raise HTTPException(404, "unknown session")
    return SESSIONS[sid]


def _series(source: Any, metrics: list[str]) -> list[dict]:
    now = source.now()
    matrix = source.metrics(None, now - CHART_SECONDS, now, step=5)["data"]["result"]
    by_name = {r["metric"]["__name__"]: r["values"] for r in matrix}
    return [
        {"metric": m, "points": [[int(t), float(v)] for t, v in by_name.get(m, [])]}
        for m in metrics
        if m in by_name
    ]


def _open(index: int, case: str) -> Session:
    source = ri.replay(case)
    overview = dispatch(source, "get_metrics", {"start": -600, "end": 0})
    logs = dispatch(source, "search_logs", {"pattern": LOG_PATTERN, "start": -600, "end": 0})
    frontend = dispatch(source, "get_metrics", {"service": "frontend", "start": -600, "end": 0})
    slo = next(
        (m for m in frontend["metrics"] if m["metric"] == "frontend_latency-90"),
        None,
    )
    top = overview["metrics"][:4]
    ratio = None
    if slo and slo["baseline_mean"]:
        ratio = slo["recent_mean"] / slo["baseline_mean"]
    if ratio and ratio >= 1.2:
        title = f"Checkout path slow: frontend p90 latency x{ratio:.1f} in the last 10 min"
        severity = "critical" if ratio >= 2 else "major"
    else:
        strong = sum(1 for m in overview["metrics"] if abs(m["z_score"]) >= 4)
        services = len({service_from_metric(m["metric"]) for m in overview["metrics"][:8]})
        title = f"Online Boutique degraded: {strong} metrics beyond 4σ across {services} services"
        severity = "major"
    opened = {
        "alert": {
            "title": title,
            "severity": severity,
            "slo": slo,
            "fired_at": source.now() - 300,
            "symptoms": top,
        },
        "logs": logs,
        "overview": overview["metrics"],
        "topology": source.topology(),
        "series": _series(source, [m["metric"] for m in top] + ["frontend_latency-90"]),
    }
    session = Session(id=secrets.token_hex(6), index=index, case=case, source=source, opened=opened)
    session.log("system", "alert", title)
    session.log(
        "system",
        "telemetry",
        f"Replay opened as anonymous case {source.case_id}; clock={source.clock_source}",
    )
    return session


def _summary(tool: str | None, result: Any) -> str:
    if not tool:
        return "Final answer"
    if not isinstance(result, dict) or "error" in result:
        return f"Tool error: {result.get('error') if isinstance(result, dict) else result}"
    if tool == "get_metrics":
        rows = result.get("metrics", [])
        if not rows:
            return "No metrics in window"
        lead = rows[0]
        return f"{len(rows)} metrics · strongest change {lead['metric']} (z={lead['z_score']:.1f})"
    if tool == "search_logs":
        return (
            f"{result.get('count', 0)} matching log lines "
            f"(baseline {result.get('baseline_count', 0)})"
        )
    if tool == "get_topology":
        return f"{len(result.get('services', []))} services · {len(result.get('edges', []))} calls"
    return "ok"


def _record_step(session: Session, step: dict, result: Any) -> None:
    with session.lock:
        entry = {**step, "summary": _summary(step.get("tool"), result)}
        session.agent["steps"].append(entry)
        if step.get("evidence_id") and result is not None:
            session.agent["evidence"][step["evidence_id"]] = result


def _diagnosed(session: Session, trajectory: dict) -> None:
    with session.lock:
        session.trajectory = trajectory
        session.candidates = ri.candidates(trajectory)
        top = session.candidates[0].service if session.candidates else None
        session.fault, session.fault_metric = (
            ri.fault_hint(trajectory, top) if top else ("unknown", None)
        )
        session.agent["status"] = "done"
        session.agent["seconds"] = round(time.time() - session.agent["started"], 1)
        session.log(
            "agent",
            "diagnosis",
            "Ranked "
            + " > ".join(trajectory.get("top_services", [])[:3])
            + f" after {trajectory.get('tool_calls', 0)} tool calls",
        )
        if not session.candidates:
            session.status = "escalated"
            session.log("planner", "escalate", "No candidates: escalate to on-call (PB-10)")
            return
        plan = draft_plan(
            incident_id=session.source.case_id,
            candidates=session.candidates,
            fault_type=session.fault,
        )
        _propose(session, plan, "Planner mapped the top-1 candidate to the playbook")


def _propose(session: Session, plan: RemediationPlan, why: str) -> None:
    session.gate.submit(plan)
    session.plans.append(plan)
    session.status = "awaiting_approval"
    session.log(
        "planner",
        "plan",
        f"{why}: {plan.playbook_id} {plan.action} on {plan.target_service} "
        f"(risk {plan.risk.value})",
    )


def _run_live(session: Session, model: str) -> None:
    from rca_agent.llm.react_loop import run_react
    from rca_agent.llm.vllm_client import VLLMClient

    try:
        llm = VLLMClient(base_url=LLM_URL, model=model, timeout=300)
        trajectory = run_react(
            llm,
            session.source,
            case_id=session.source.case_id,
            on_step=lambda step, result: _record_step(session, step, result),
        )
        _diagnosed(session, trajectory)
    except Exception as exc:  # surfaced to the operator, not swallowed
        with session.lock:
            session.agent.update(status="error", error=str(exc))
            session.status = "detected"
            session.log("agent", "error", f"Agent failed: {exc}")


def _evidence_from_messages(trajectory: dict) -> dict[str, Any]:
    evidence = {}
    for message in trajectory.get("messages", []):
        if message.get("role") != "tool":
            continue
        try:
            content = json.loads(message["content"])
        except (json.JSONDecodeError, TypeError):
            continue
        if isinstance(content, dict) and content.get("id"):
            evidence[content["id"]] = content
    return evidence


def _run_saved(session: Session, trajectory: dict) -> None:
    evidence = _evidence_from_messages(trajectory)
    for step in trajectory.get("steps", []):
        time.sleep(SAVED_STEP_DELAY)
        _record_step(session, step, evidence.get(step.get("evidence_id")))
    _diagnosed(session, trajectory)


def _plan_view(session: Session, plan: RemediationPlan) -> dict:
    record = session.gate.latest(plan.id)
    return {
        **plan.model_dump(mode="json"),
        "decision": record.model_dump(mode="json") if record else None,
    }


def _view(session: Session) -> dict:
    with session.lock:
        trajectory = session.trajectory or {}
        return {
            "id": session.id,
            "label": _incident_label(session.index),
            "case_id": session.source.case_id,
            "now": session.source.now(),
            "clock_source": session.source.clock_source,
            "status": session.status,
            **session.opened,
            "agent": {**session.agent, "budget": 12},
            "diagnosis": (
                {
                    "top_services": trajectory.get("top_services", []),
                    "claims": trajectory.get("claims", []),
                    "candidates": [c.model_dump(mode="json") for c in session.candidates],
                    "fault": session.fault,
                    "fault_metric": session.fault_metric,
                    "tool_calls": trajectory.get("tool_calls", 0),
                    "invalid_tool_calls": trajectory.get("invalid_tool_calls", 0),
                    "unknown_services": trajectory.get("unknown_services", []),
                    "unsupported_claims": trajectory.get("unsupported_claims", 0),
                    "status": trajectory.get("status"),
                }
                if session.trajectory
                else None
            ),
            "plans": [_plan_view(session, p) for p in session.plans],
            "attempts": session.attempts,
            "audit": list(session.audit),
            "revealed": session.revealed,
        }


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {
        "llm_model": ri.server_model(LLM_URL),
        "llm_url": LLM_URL,
        "cases": len(ri.demo_cases()),
    }


@app.get("/api/incidents")
def incidents() -> list[dict]:
    opened = {s.index: s for s in SESSIONS.values()}
    return [
        {
            "index": i,
            "label": _incident_label(i),
            "session": opened[i].id if i in opened else None,
            "status": opened[i].status if i in opened else "new",
        }
        for i, _ in enumerate(ri.demo_cases())
    ]


@app.post("/api/incidents/{index}/open")
def open_incident(index: int) -> dict:
    cases = ri.demo_cases()
    if not 0 <= index < len(cases):
        raise HTTPException(404, "unknown incident")
    for session in SESSIONS.values():
        if session.index == index:
            return _view(session)
    session = _open(index, cases[index])
    SESSIONS[session.id] = session
    return _view(session)


@app.post("/api/incidents/{index}/reset")
def reset_incident(index: int) -> dict:
    for sid in [s.id for s in SESSIONS.values() if s.index == index]:
        del SESSIONS[sid]
    return open_incident(index)


@app.get("/api/sessions/{sid}")
def get_session(sid: str) -> dict:
    return _view(_session(sid))


@app.post("/api/sessions/{sid}/investigate")
def investigate(sid: str, request: InvestigateRequest) -> dict:
    session = _session(sid)
    if session.agent["status"] == "running":
        raise HTTPException(409, "investigation already running")
    if request.mode == "live":
        model = ri.server_model(LLM_URL)
        if not model:
            raise HTTPException(503, f"No LLM server at {LLM_URL}")
        target, args = _run_live, (session, model)
    else:
        saved = ri.saved_trajectory(session.case)
        if saved is None:
            raise HTTPException(404, "no recorded run for this incident")
        model = f"{ri.SAVED_RUN} (recorded)"
        target, args = _run_saved, (session, saved)
    with session.lock:
        session.agent.update(
            status="running",
            mode=request.mode,
            model=model,
            steps=[],
            evidence={},
            error=None,
            started=time.time(),
            seconds=None,
        )
        session.trajectory, session.candidates, session.plans = None, [], []
        session.attempts, session.failed_services = [], []
        session.status = "investigating"
        session.log("agent", "start", f"Investigation started ({request.mode}, {model})")
    threading.Thread(target=target, args=args, daemon=True).start()
    return _view(session)


@app.post("/api/sessions/{sid}/decision")
def decide(sid: str, request: DecisionRequest) -> dict:
    session = _session(sid)
    if session.status != "awaiting_approval" or not session.plans:
        raise HTTPException(409, "no plan is awaiting approval")
    if not request.operator.strip():
        raise HTTPException(422, "operator id is required")
    plan = session.plans[-1]
    approve = request.decision == "approve"
    record = session.gate.decide(
        plan.id,
        decision=ApprovalDecision.APPROVE if approve else ApprovalDecision.REJECT,
        operator=request.operator.strip(),
        note=request.note,
    )
    result = session.executor.execute(plan, approval_id=record.id, approved=approve)
    attempt = {
        "plan_id": plan.id,
        "target": plan.target_service,
        "action": plan.action,
        "approval": record.model_dump(mode="json"),
        "execution": result.model_dump(mode="json"),
        "verification": None,
    }
    with session.lock:
        session.attempts.append(attempt)
        session.log(
            request.operator.strip(),
            "approval" if approve else "rejection",
            f"{'Approved' if approve else 'Rejected'} {plan.action} on {plan.target_service}"
            + (f": {request.note}" if request.note else ""),
        )
        session.log("executor", "execute", result.detail)
        if not approve:
            session.status = "rejected"
        elif plan.action == "escalate_manual":
            session.status = "escalated"
        else:
            session.status = "verifying"
    return _view(session)


@app.post("/api/sessions/{sid}/replan")
def replan(sid: str, request: VerifyRequest) -> dict:
    """After a rejection or a failed remedy: draft for the next candidate."""
    session = _session(sid)
    if session.status not in {"rejected", "verifying"} or not session.plans:
        raise HTTPException(409, "nothing to re-plan")
    failed = session.plans[-1].target_service
    with session.lock:
        session.failed_services.append(failed)
        remaining = [c for c in session.candidates if c.service not in session.failed_services]
        fault = "unknown"
        if remaining:
            fault, _ = ri.fault_hint(session.trajectory or {}, remaining[0].service)
        plan = next_plan_after_failure(
            incident_id=session.source.case_id,
            candidates=[c for c in session.candidates if c.service == failed] + remaining,
            fault_type=fault if fault != "unknown" else session.fault,
            failed_service=failed,
        )
        reason = "next candidate" if remaining else "top-k exhausted, escalate"
        _propose(session, plan, f"Feedback loop: {failed} ruled out, {reason}")
    return _view(session)


@app.post("/api/sessions/{sid}/verify")
def verify(sid: str, request: VerifyRequest) -> dict:
    session = _session(sid)
    if session.status != "verifying" or not session.attempts:
        raise HTTPException(409, "no executed remedy to verify")
    plan = session.plans[-1]
    if request.outcome == "simulate":
        recovered = plan.target_service == ri.truth(session.case)[0]
        method = "simulated from the benchmark label (replay only; live SLO check in 295B)"
    else:
        recovered = request.outcome == "recovered"
        method = f"reported by {request.operator}"
    with session.lock:
        session.attempts[-1]["verification"] = {"recovered": recovered, "method": method}
        session.log(
            "verifier",
            "verify",
            f"{'SLO recovered' if recovered else 'Still failing'} after {plan.action} on "
            f"{plan.target_service} ({method})",
        )
        if recovered:
            session.status = "resolved"
    if not recovered:
        return replan(sid, request)
    return _view(session)


@app.post("/api/sessions/{sid}/reveal")
def reveal(sid: str) -> dict:
    session = _session(sid)
    service, fault = ri.truth(session.case)
    tops = (session.trajectory or {}).get("top_services", [])
    with session.lock:
        session.revealed = {
            "service": service,
            "fault": fault,
            "agent_rank": tops.index(service) + 1 if service in tops else None,
            "baselines": ri.baseline_rankings(session.case),
        }
        session.log("operator", "reveal", f"Ground truth revealed: {service} ({fault})")
    return _view(session)


@app.get("/api/evaluation")
def evaluation() -> dict:
    report = ri.n1_results() or {}
    return {
        "n1": report,
        "runs": [{k: v for k, v in r.items()} for r in ri.run_summaries()],
        "failure_modes": FAILURE_MODES.read_text() if FAILURE_MODES.exists() else "",
        "planner": json.loads(PLANNER_EVAL.read_text()) if PLANNER_EVAL.exists() else None,
    }
