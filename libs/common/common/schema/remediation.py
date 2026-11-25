"""Remediation plan, approval, and execution records (E7–E10)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class RiskLevel(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ApprovalDecision(StrEnum):
    APPROVE = "approve"
    EDIT = "edit"
    REJECT = "reject"


class ExecutionStatus(StrEnum):
    DRY_RUN = "dry_run"
    SUCCESS = "success"
    REJECTED = "rejected"
    FAILED = "failed"


class RemediationPlan(BaseModel):
    """Structured fix suggestion only — never executes by itself (E7)."""

    id: str
    incident_id: str
    playbook_id: str
    action: str
    target_service: str
    namespace: str
    params: dict[str, Any] = Field(default_factory=dict)
    rationale: str = ""
    risk: RiskLevel = RiskLevel.MEDIUM
    undo: str = ""
    fault_type: str = ""
    rank: int = 1
    confidence: float = 0.0
    secondary: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Optional alternate remedies for top-2 / top-3",
    )


class ApprovalRecord(BaseModel):
    """Append-only audit entry for a human decision (E8, E10)."""

    id: str
    plan_id: str
    decision: ApprovalDecision
    operator: str
    decided_at: datetime
    note: str = ""
    edited_action: str | None = None


class ExecutionResult(BaseModel):
    """Outcome of the allowlisted executor (E9)."""

    id: str
    plan_id: str
    approval_id: str | None
    action: str
    target_service: str
    namespace: str
    status: ExecutionStatus
    dry_run: bool = True
    detail: str = ""
    executed_at: datetime
