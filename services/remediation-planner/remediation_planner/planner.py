"""If-then playbook mapper: diagnosis → structured RemediationPlan."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

import yaml
from common.schema import Candidate, RemediationPlan, RiskLevel

# Aliases so Chaos Mesh / RCAEval / scenario names hit the same playbook rows.
_FAULT_ALIASES: dict[str, str] = {
    "pod-kill": "pod_crash",
    "pod_kill": "pod_crash",
    "pod-crash": "pod_crash",
    "pod_crash": "pod_crash",
    "cpu-stress": "cpu",
    "cpu_stress": "cpu",
    "cpu": "cpu",
    "mem": "mem",
    "memory": "mem",
    "delay": "delay",
    "loss": "loss",
    "disk": "disk",
    "socket": "socket",
    "bad_deploy": "bad_deploy",
    "bad-deployment": "bad_deploy",
    "f1": "f1",
    "f2": "f1",
    "f3": "f1",
    "f4": "f1",
    "f5": "f1",
    "unknown": "unknown",
}


def _default_playbook_path() -> Path:
    here = Path(__file__).resolve().parent.parent
    candidate = here / "remediation_playbook.yaml"
    if candidate.is_file():
        return candidate
    # Fall back to 295A package copy if present beside the monorepo.
    for parent in here.parents:
        alt = parent / "295A_Design_Validation" / "playbook" / "remediation_playbook.yaml"
        if alt.is_file():
            return alt
    return candidate


def load_playbook(path: str | Path | None = None) -> dict[str, Any]:
    p = Path(path) if path else _default_playbook_path()
    with p.open(encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict) or "entries" not in data:
        raise ValueError(f"Invalid playbook at {p}")
    return data


def normalize_fault(fault_type: str) -> str:
    key = (fault_type or "unknown").strip().lower()
    return _FAULT_ALIASES.get(key, _FAULT_ALIASES.get(key.replace("-", "_"), "unknown"))


def _find_entry(playbook: dict[str, Any], fault_type: str) -> dict[str, Any]:
    norm = normalize_fault(fault_type)
    for entry in playbook.get("entries", []):
        if str(entry.get("fault_type", "")).lower() == norm:
            return entry
    for entry in playbook.get("entries", []):
        if str(entry.get("fault_type", "")).lower() == "unknown":
            return entry
    raise KeyError(f"No playbook row for fault_type={fault_type!r}")


def _risk(value: str) -> RiskLevel:
    try:
        return RiskLevel(value.lower())
    except ValueError:
        return RiskLevel.MEDIUM


def draft_plan(
    *,
    incident_id: str,
    candidates: list[Candidate],
    fault_type: str,
    namespace: str = "online-boutique",
    playbook: dict[str, Any] | None = None,
    include_secondaries: bool = True,
) -> RemediationPlan:
    """Map top-1 (and optionally top-2/3) to allowlisted playbook actions."""
    if not candidates:
        raise ValueError("Cannot draft a plan without ranked candidates")

    book = playbook or load_playbook()
    top = candidates[0]
    entry = _find_entry(book, fault_type)
    action = str(entry.get("primary_action", "escalate_manual"))

    secondary: list[dict[str, Any]] = []
    if include_secondaries:
        for cand in candidates[1:3]:
            secondary.append(
                {
                    "rank": cand.rank,
                    "service": cand.service,
                    "confidence": cand.confidence,
                    "action": action
                    if cand.service == top.service
                    else str(entry.get("alternate_action", action)),
                    "playbook_id": entry.get("id"),
                }
            )

    return RemediationPlan(
        id=f"plan-{uuid.uuid4().hex[:10]}",
        incident_id=incident_id,
        playbook_id=str(entry.get("id", "unknown")),
        action=action,
        target_service=top.service,
        namespace=namespace,
        params=dict(entry.get("params") or {}),
        rationale=str(entry.get("rationale", "")),
        risk=_risk(str(entry.get("risk", "medium"))),
        undo=str(entry.get("undo", "")),
        fault_type=normalize_fault(fault_type),
        rank=top.rank,
        confidence=float(top.confidence),
        secondary=secondary,
    )


def next_plan_after_failure(
    *,
    incident_id: str,
    candidates: list[Candidate],
    fault_type: str,
    failed_service: str,
    namespace: str = "online-boutique",
    playbook: dict[str, Any] | None = None,
) -> RemediationPlan:
    """Feedback loop: skip the failed service and draft for the next candidate."""
    remaining = [c for c in candidates if c.service != failed_service]
    if not remaining:
        # Exhausted top-k → escalate
        book = playbook or load_playbook()
        entry = _find_entry(book, "unknown")
        return RemediationPlan(
            id=f"plan-{uuid.uuid4().hex[:10]}",
            incident_id=incident_id,
            playbook_id=str(entry.get("id", "PB-10")),
            action="escalate_manual",
            target_service=failed_service,
            namespace=namespace,
            rationale="Top-k exhausted after failed remediation; escalate to human.",
            risk=RiskLevel.HIGH,
            undo="n/a",
            fault_type="unknown",
            rank=0,
            confidence=0.0,
        )
    # Re-number ranks for clarity
    renumbered = [c.model_copy(update={"rank": i + 1}) for i, c in enumerate(remaining)]
    return draft_plan(
        incident_id=incident_id,
        candidates=renumbered,
        fault_type=fault_type,
        namespace=namespace,
        playbook=playbook,
    )
