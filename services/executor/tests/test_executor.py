"""Allowlisted executor tests (E9)."""

from common.schema import ExecutionStatus, RemediationPlan, RiskLevel
from executor import AllowlistedExecutor


def _plan(action: str = "restart_pod", namespace: str = "online-boutique") -> RemediationPlan:
    return RemediationPlan(
        id="plan-x",
        incident_id="inc-1",
        playbook_id="PB-01",
        action=action,
        target_service="checkoutservice",
        namespace=namespace,
        risk=RiskLevel.LOW,
    )


def test_rejects_without_approval():
    ex = AllowlistedExecutor(dry_run=True)
    result = ex.execute(_plan(), approval_id=None, approved=False)
    assert result.status == ExecutionStatus.REJECTED


def test_rejects_unknown_action():
    ex = AllowlistedExecutor(dry_run=True)
    result = ex.execute(_plan(action="rm -rf /"), approval_id="appr-1", approved=True)
    assert result.status == ExecutionStatus.REJECTED
    assert "allowlist" in result.detail.lower()


def test_rejects_bad_namespace():
    ex = AllowlistedExecutor(dry_run=True)
    result = ex.execute(
        _plan(namespace="kube-system"),
        approval_id="appr-1",
        approved=True,
    )
    assert result.status == ExecutionStatus.REJECTED


def test_dry_run_success():
    ex = AllowlistedExecutor(dry_run=True)
    result = ex.execute(_plan(), approval_id="appr-1", approved=True)
    assert result.status == ExecutionStatus.DRY_RUN
    assert "DRY-RUN" in result.detail
