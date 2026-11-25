"""Remediation planner playbook tests (E7)."""

from common.schema import Candidate
from remediation_planner import draft_plan, load_playbook, next_plan_after_failure
from remediation_planner.planner import normalize_fault


def test_normalize_scenario_fault_aliases():
    assert normalize_fault("pod-kill") == "pod_crash"
    assert normalize_fault("cpu-stress") == "cpu"


def test_draft_plan_maps_cpu_stress_to_playbook():
    cands = [
        Candidate(service="cartservice", score=0.9, rank=1, confidence=0.9),
        Candidate(service="frontend", score=0.4, rank=2, confidence=0.4),
    ]
    plan = draft_plan(
        incident_id="inc-0001",
        candidates=cands,
        fault_type="cpu-stress",
        namespace="online-boutique",
    )
    assert plan.target_service == "cartservice"
    assert plan.action in {"set_cpu_limit", "scale_deployment", "restart_pod"}
    assert plan.playbook_id.startswith("PB-")
    assert len(plan.secondary) == 1


def test_feedback_loop_escalates_when_exhausted():
    cands = [Candidate(service="cartservice", score=0.9, rank=1, confidence=0.9)]
    plan = next_plan_after_failure(
        incident_id="inc-0001",
        candidates=cands,
        fault_type="cpu",
        failed_service="cartservice",
    )
    assert plan.action == "escalate_manual"


def test_playbook_loads():
    book = load_playbook()
    assert "entries" in book
    assert len(book["entries"]) >= 8
