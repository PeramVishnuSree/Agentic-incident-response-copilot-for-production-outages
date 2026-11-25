"""Preliminary planner evaluation on the 30 real agent diagnoses (RE2-OB, one case per
service x fault).

For each saved trajectory: agent ranking -> fault family from evidence -> playbook plan,
then the failed-remedy feedback loop is replayed against the benchmark label.

    uv run python -m eval.planner_eval
"""

from __future__ import annotations

import json
from collections import Counter

from rca_agent.tools.telemetry import get_metrics
from remediation_planner import draft_plan, load_playbook, next_plan_after_failure

from console import real_incident as ri
from eval.rcaeval.common import ARTIFACTS

OUT = ARTIFACTS / "planner"
PLAYBOOK_BY_FAULT = {e["fault_type"]: e for e in load_playbook()["entries"] if e.get("fault_type")}


RULES = ("max", "resource_first")


def fault_classification_all_cases() -> dict:
    """Fault-family accuracy on all 90 cases given the true service (isolates the
    classification step from the agent's ranking)."""
    hits = {rule: Counter() for rule in RULES}
    totals: Counter = Counter()
    for path in sorted(ri.CASE_ROOT.iterdir()):
        if not path.is_dir():
            continue
        service, fault = ri.truth(path.name)
        rows = get_metrics(ri.replay(path.name), {"service": service, "start": -600, "end": 0})
        totals[fault] += 1
        for rule in RULES:
            hits[rule][fault] += (
                ri.classify_fault(rows.get("metrics", []), service, rule)[0] == fault
            )
    n = sum(totals.values())
    return {
        "n_cases": n,
        "note": "true service given; window = 10 min before the clock vs the 10 min before that",
        **{
            rule: {
                "accuracy": sum(hits[rule].values()) / n,
                "by_fault": {f: hits[rule][f] / totals[f] for f in sorted(totals)},
            }
            for rule in RULES
        },
    }


def evaluate_case(case: str, rule: str = "resource_first") -> dict:
    trajectory = ri.saved_trajectory(case)
    service, fault = ri.truth(case)
    cands = ri.candidates(trajectory)
    hint, metric = ri.fault_hint(trajectory, cands[0].service, rule) if cands else ("unknown", None)
    plan = draft_plan(incident_id=case, candidates=cands, fault_type=hint)
    attempts = [plan]
    failed: list[str] = []
    while attempts[-1].target_service != service and attempts[-1].action != "escalate_manual":
        failed.append(attempts[-1].target_service)
        remaining = [c for c in cands if c.service not in failed]
        next_hint = (
            ri.fault_hint(trajectory, remaining[0].service, rule)[0] if remaining else "unknown"
        )
        attempts.append(
            next_plan_after_failure(
                incident_id=case,
                candidates=[c for c in cands if c.service == failed[-1]] + remaining,
                fault_type=next_hint,
                failed_service=failed[-1],
            )
        )
    final = attempts[-1]
    resolved = final.target_service == service and final.action != "escalate_manual"
    ideal = PLAYBOOK_BY_FAULT.get(fault, {}).get("id")
    return {
        "case": case,
        "true_service": service,
        "true_fault": fault,
        "agent_top3": [c.service for c in cands[:3]],
        "fault_hint": hint,
        "fault_hint_metric": metric,
        "first_plan": {
            "playbook_id": plan.playbook_id,
            "action": plan.action,
            "target": plan.target_service,
        },
        "target_correct": plan.target_service == service,
        "playbook_matches_true_fault": plan.playbook_id == ideal,
        "fully_correct_first_plan": plan.target_service == service and plan.playbook_id == ideal,
        "escalated_first": plan.action == "escalate_manual",
        "approvals_needed": len(attempts),
        "resolved_by_loop": resolved,
        "wrong_target_writes_proposed": sum(
            1 for p in attempts if p.target_service != service and p.action != "escalate_manual"
        ),
    }


def summarize(rule: str) -> tuple[dict, list[dict]]:
    rows = [evaluate_case(c, rule) for c in ri.demo_cases() if ri.saved_trajectory(c)]
    n = len(rows)
    approvals = Counter(r["approvals_needed"] for r in rows if r["resolved_by_loop"])
    by_fault: dict[str, dict] = {}
    for fault in sorted({r["true_fault"] for r in rows}):
        sub = [r for r in rows if r["true_fault"] == fault]
        by_fault[fault] = {
            "n": len(sub),
            "fault_hint_correct": sum(r["fault_hint"] == fault for r in sub) / len(sub),
            "hints": dict(Counter(r["fault_hint"] for r in sub)),
            "first_plan_target_correct": sum(r["target_correct"] for r in sub) / len(sub),
        }
    summary = {
        "n_cases": n,
        "rule": rule,
        "source_run": ri.SAVED_RUN,
        "first_plan_target_correct": sum(r["target_correct"] for r in rows) / n,
        "fault_hint_correct": sum(r["fault_hint"] == r["true_fault"] for r in rows) / n,
        "playbook_matches_true_fault": sum(r["playbook_matches_true_fault"] for r in rows) / n,
        "fully_correct_first_plan": sum(r["fully_correct_first_plan"] for r in rows) / n,
        "escalated_first_plan": sum(r["escalated_first"] for r in rows) / n,
        "resolved_within_k_approvals": {
            str(k): sum(v for kk, v in approvals.items() if kk <= k) / n for k in (1, 2, 3)
        },
        "mean_approvals_when_resolved": (
            sum(k * v for k, v in approvals.items()) / max(1, sum(approvals.values()))
        ),
        "wrong_target_write_proposals_per_incident": sum(
            r["wrong_target_writes_proposed"] for r in rows
        )
        / n,
        "by_fault": by_fault,
    }
    return summary, rows


def main() -> None:
    result = {"fault_classification_90": fault_classification_all_cases()}
    for rule in RULES:
        summary, rows = summarize(rule)
        result[f"planner_30_{rule}"] = {"summary": summary, "cases": rows}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "planner_eval.json").write_text(json.dumps(result, indent=2))
    print(json.dumps(result["fault_classification_90"], indent=2))
    for rule in RULES:
        s = {k: v for k, v in result[f"planner_30_{rule}"]["summary"].items() if k != "by_fault"}
        print(json.dumps(s, indent=2))


if __name__ == "__main__":
    main()
