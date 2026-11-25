"""In-memory approval gate with append-only audit log (295A prototype)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from common.schema import ApprovalDecision, ApprovalRecord, RemediationPlan


class ApprovalGate:
    """Operator must approve before any executor call.

    295A prototype keeps the audit log in memory. 295B persists to Postgres.
    """

    def __init__(self) -> None:
        self._log: list[ApprovalRecord] = []
        self._plans: dict[str, RemediationPlan] = {}

    def submit(self, plan: RemediationPlan) -> RemediationPlan:
        self._plans[plan.id] = plan
        return plan

    def decide(
        self,
        plan_id: str,
        *,
        decision: ApprovalDecision,
        operator: str,
        note: str = "",
        edited_action: str | None = None,
    ) -> ApprovalRecord:
        if plan_id not in self._plans:
            raise KeyError(f"Unknown plan_id={plan_id}")
        if not operator.strip():
            raise ValueError("operator identity required for audit")
        record = ApprovalRecord(
            id=f"appr-{uuid.uuid4().hex[:10]}",
            plan_id=plan_id,
            decision=decision,
            operator=operator.strip(),
            decided_at=datetime.now(tz=UTC),
            note=note,
            edited_action=edited_action,
        )
        self._log.append(record)
        return record

    def is_approved(self, plan_id: str) -> bool:
        for rec in reversed(self._log):
            if rec.plan_id == plan_id:
                return rec.decision in {ApprovalDecision.APPROVE, ApprovalDecision.EDIT}
        return False

    def latest(self, plan_id: str) -> ApprovalRecord | None:
        for rec in reversed(self._log):
            if rec.plan_id == plan_id:
                return rec
        return None

    @property
    def audit_log(self) -> list[ApprovalRecord]:
        return list(self._log)
