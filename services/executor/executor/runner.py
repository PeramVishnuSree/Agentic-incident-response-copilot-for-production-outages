"""Execute only allowlisted actions after a recorded approval.

295A default is dry_run=True (no real cluster writes). Live kubectl apply is 295B.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from common.config import get_settings
from common.schema import ExecutionResult, ExecutionStatus, RemediationPlan

# Canonical allowlist for the early prototype.
ALLOWLISTED_ACTIONS: frozenset[str] = frozenset(
    {
        "restart_pod",
        "rollout_restart",
        "rollout-restart",
        "delete_pod_for_reschedule",
        "scale_deployment",
        "set_cpu_limit",
        "set_memory_limit",
        "rollback_deployment",
        "escalate_manual",
    }
)


class AllowlistedExecutor:
    def __init__(
        self,
        *,
        dry_run: bool = True,
        allowed_namespaces: set[str] | None = None,
        allowed_actions: frozenset[str] | None = None,
    ) -> None:
        settings = get_settings()
        self.dry_run = dry_run
        self.allowed_namespaces = allowed_namespaces or settings.allowed_namespaces
        self.allowed_actions = allowed_actions or ALLOWLISTED_ACTIONS
        self._history: list[ExecutionResult] = []

    def execute(
        self,
        plan: RemediationPlan,
        *,
        approval_id: str | None,
        approved: bool,
    ) -> ExecutionResult:
        now = datetime.now(tz=UTC)
        action = plan.action
        ns = plan.namespace

        if not approved or not approval_id:
            result = ExecutionResult(
                id=f"exec-{uuid.uuid4().hex[:10]}",
                plan_id=plan.id,
                approval_id=approval_id,
                action=action,
                target_service=plan.target_service,
                namespace=ns,
                status=ExecutionStatus.REJECTED,
                dry_run=self.dry_run,
                detail="Rejected: missing human approval record",
                executed_at=now,
            )
            self._history.append(result)
            return result

        if action not in self.allowed_actions:
            result = ExecutionResult(
                id=f"exec-{uuid.uuid4().hex[:10]}",
                plan_id=plan.id,
                approval_id=approval_id,
                action=action,
                target_service=plan.target_service,
                namespace=ns,
                status=ExecutionStatus.REJECTED,
                dry_run=self.dry_run,
                detail=f"Rejected: action {action!r} not on allowlist",
                executed_at=now,
            )
            self._history.append(result)
            return result

        if ns not in self.allowed_namespaces:
            result = ExecutionResult(
                id=f"exec-{uuid.uuid4().hex[:10]}",
                plan_id=plan.id,
                approval_id=approval_id,
                action=action,
                target_service=plan.target_service,
                namespace=ns,
                status=ExecutionStatus.REJECTED,
                dry_run=self.dry_run,
                detail=f"Rejected: namespace {ns!r} not allowlisted",
                executed_at=now,
            )
            self._history.append(result)
            return result

        if action == "escalate_manual":
            detail = "Escalated to human operator (no cluster mutation)."
            status = ExecutionStatus.SUCCESS if not self.dry_run else ExecutionStatus.DRY_RUN
        elif self.dry_run:
            detail = (
                f"DRY-RUN: would run {action} on deploy/{plan.target_service} "
                f"in {ns} with params={plan.params}"
            )
            status = ExecutionStatus.DRY_RUN
        else:
            # Live path reserved for 295B (kubectl). Keep safe stub for now.
            detail = (
                f"LIVE STUB (295B): recorded intent {action} on "
                f"{plan.target_service}/{ns}; wire kubectl here."
            )
            status = ExecutionStatus.SUCCESS

        result = ExecutionResult(
            id=f"exec-{uuid.uuid4().hex[:10]}",
            plan_id=plan.id,
            approval_id=approval_id,
            action=action,
            target_service=plan.target_service,
            namespace=ns,
            status=status,
            dry_run=self.dry_run,
            detail=detail,
            executed_at=now,
        )
        self._history.append(result)
        return result

    @property
    def history(self) -> list[ExecutionResult]:
        return list(self._history)
