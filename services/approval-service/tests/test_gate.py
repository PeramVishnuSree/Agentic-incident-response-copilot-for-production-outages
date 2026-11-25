"""Approval gate + audit log tests (E8, E10)."""

import pytest
from approval_service import ApprovalGate
from common.schema import ApprovalDecision, RemediationPlan, RiskLevel


def _plan() -> RemediationPlan:
    return RemediationPlan(
        id="plan-test1",
        incident_id="inc-1",
        playbook_id="PB-02",
        action="set_cpu_limit",
        target_service="cartservice",
        namespace="online-boutique",
        risk=RiskLevel.MEDIUM,
    )


def test_approve_records_audit():
    gate = ApprovalGate()
    gate.submit(_plan())
    rec = gate.decide("plan-test1", decision=ApprovalDecision.APPROVE, operator="alice")
    assert gate.is_approved("plan-test1")
    assert rec.operator == "alice"
    assert len(gate.audit_log) == 1


def test_reject_not_approved():
    gate = ApprovalGate()
    gate.submit(_plan())
    gate.decide("plan-test1", decision=ApprovalDecision.REJECT, operator="bob")
    assert gate.is_approved("plan-test1") is False


def test_operator_required():
    gate = ApprovalGate()
    gate.submit(_plan())
    with pytest.raises(ValueError):
        gate.decide("plan-test1", decision=ApprovalDecision.APPROVE, operator="  ")
