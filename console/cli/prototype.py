#!/usr/bin/env python3
"""CMPE 295A early vertical prototype (offline demo).

Flow: synthetic fault signals → correlate/RCA → playbook plan → human approve
→ allowlisted executor (dry-run).

No live cluster required. Chaos Mesh scenarios remain available via `make scenario-*`.

Team integration (each stage owned):
  Gandham  — synthetic telemetry signals (gateway schema) + scenarios ground truth
  Patrini  — correlation engine + read-only RCA agent
  Peram    — remediation planner + approval gate + allowlisted executor
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import yaml
from approval_service import ApprovalGate
from common.schema import ApprovalDecision, Event, Severity, SignalType
from executor import AllowlistedExecutor
from rca_agent.graph import run_diagnosis_with_mock
from remediation_planner import draft_plan, next_plan_after_failure

REPO_ROOT = Path(__file__).resolve().parents[2]
REGISTRY = REPO_ROOT / "scenarios" / "registry.yaml"


def _load_ground_truth(scenario_id: str) -> dict:
    with REGISTRY.open(encoding="utf-8") as f:
        reg = yaml.safe_load(f)
    entry = reg["scenarios"][scenario_id]
    gt_path = REPO_ROOT / entry["ground_truth"]
    with gt_path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def synthesize_signals(gt: dict, *, now: datetime | None = None) -> list[Event]:
    """Gandham path: emulate gateway-normalized events from scenario ground truth."""
    t0 = now or datetime.now(tz=UTC)
    root = gt["root_cause_service"]
    ns = gt.get("root_cause_namespace", "online-boutique")
    cascade = list(gt.get("expected_cascade") or [])
    events: list[Event] = [
        Event(
            time=t0,
            service=root,
            pod=f"{root}-0",
            namespace=ns,
            type=SignalType.ALERT,
            severity=Severity.CRITICAL,
            raw_ref=f"alert://{root}/primary",
            labels={"fault": str(gt.get("fault_type", "unknown")), "role": "root"},
        ),
        Event(
            time=t0 + timedelta(seconds=5),
            service=root,
            pod=f"{root}-0",
            namespace=ns,
            type=SignalType.METRIC,
            severity=Severity.ERROR,
            raw_ref=f"metric://{root}/anomaly",
            labels={"role": "root"},
        ),
    ]
    for i, svc in enumerate(cascade):
        events.append(
            Event(
                time=t0 + timedelta(seconds=10 + 5 * i),
                service=svc,
                pod=f"{svc}-0",
                namespace=ns,
                type=SignalType.ALERT,
                severity=Severity.WARNING if i else Severity.ERROR,
                raw_ref=f"alert://{svc}/cascade-{i}",
                labels={"role": "cascade"},
            )
        )
    return events


def run_prototype(
    scenario: str = "cpu-stress",
    *,
    operator: str = "demo-operator",
    approve: bool = True,
    simulate_failure_loop: bool = False,
    dry_run: bool = True,
) -> dict:
    gt = _load_ground_truth(scenario)
    fault_type = str(gt.get("fault_type", "unknown"))
    ns = str(gt.get("root_cause_namespace", "online-boutique"))

    # 1) Collect / normalize (Gandham)
    signals = synthesize_signals(gt)

    # 2) Correlate + RCA (Patrini)
    diagnosis = run_diagnosis_with_mock(signals)
    if not diagnosis.incident or not diagnosis.candidates:
        raise RuntimeError("Diagnosis produced no candidates")

    # 3) Plan (Peram) — playbook lookup for top-1
    plan = draft_plan(
        incident_id=diagnosis.incident.id,
        candidates=diagnosis.candidates,
        fault_type=fault_type,
        namespace=ns,
    )

    gate = ApprovalGate()
    gate.submit(plan)
    executor = AllowlistedExecutor(dry_run=dry_run)

    # 4) Human gate (Peram)
    if approve:
        approval = gate.decide(
            plan.id,
            decision=ApprovalDecision.APPROVE,
            operator=operator,
            note="295A early prototype demo approval",
        )
    else:
        approval = gate.decide(
            plan.id,
            decision=ApprovalDecision.REJECT,
            operator=operator,
            note="demo reject path",
        )

    # 5) Execute allowlisted (Peram) — dry-run by default
    execution = executor.execute(
        plan,
        approval_id=approval.id,
        approved=gate.is_approved(plan.id),
    )

    feedback = None
    if simulate_failure_loop and approve:
        # Failed remedy → next candidate plan (still needs new approval)
        plan2 = next_plan_after_failure(
            incident_id=diagnosis.incident.id,
            candidates=diagnosis.candidates,
            fault_type=fault_type,
            failed_service=plan.target_service,
            namespace=ns,
        )
        gate.submit(plan2)
        appr2 = gate.decide(
            plan2.id,
            decision=ApprovalDecision.APPROVE,
            operator=operator,
            note="feedback-loop second attempt",
        )
        exec2 = executor.execute(plan2, approval_id=appr2.id, approved=True)
        feedback = {
            "second_plan": plan2.model_dump(mode="json"),
            "second_approval": appr2.model_dump(mode="json"),
            "second_execution": exec2.model_dump(mode="json"),
        }

    top = [
        {"rank": c.rank, "service": c.service, "score": c.score, "confidence": c.confidence}
        for c in diagnosis.candidates
    ]
    hit = any(c.service == gt["root_cause_service"] for c in diagnosis.candidates[:1])
    hit3 = any(c.service == gt["root_cause_service"] for c in diagnosis.candidates[:3])

    return {
        "scenario": scenario,
        "ground_truth": {
            "service": gt["root_cause_service"],
            "fault_type": fault_type,
        },
        "team_stages": {
            "gandham": "synthetic telemetry Event schema from scenario ground truth",
            "patrini": "correlation + RCA mock-LLM diagnosis",
            "peram": "playbook plan + approval audit + allowlisted dry-run execute",
        },
        "signals": len(signals),
        "diagnosis_states": diagnosis.states,
        "candidates": top,
        "ac_at_1": hit,
        "ac_at_3": hit3,
        "plan": plan.model_dump(mode="json"),
        "approval": approval.model_dump(mode="json"),
        "execution": execution.model_dump(mode="json"),
        "audit_log_len": len(gate.audit_log),
        "feedback_loop": feedback,
        "notes": diagnosis.notes,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="295A early vertical prototype demo")
    parser.add_argument(
        "--scenario",
        default="cpu-stress",
        choices=["cpu-stress", "pod-crash"],
        help="Scenario id from scenarios/registry.yaml",
    )
    parser.add_argument("--operator", default="demo-operator")
    parser.add_argument("--reject", action="store_true", help="Reject instead of approve")
    parser.add_argument(
        "--feedback-loop",
        action="store_true",
        help="Simulate failed remedy → next candidate",
    )
    parser.add_argument("--live", action="store_true", help="Disable dry-run (still stubbed)")
    parser.add_argument("--pretty", action="store_true")
    args = parser.parse_args(argv)

    result = run_prototype(
        args.scenario,
        operator=args.operator,
        approve=not args.reject,
        simulate_failure_loop=args.feedback_loop,
        dry_run=not args.live,
    )
    if args.pretty:
        print(json.dumps(result, indent=2, default=str))
    else:
        print(json.dumps(result, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
