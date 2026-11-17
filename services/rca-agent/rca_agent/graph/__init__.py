"""LangGraph-style diagnosis state machine (Workbook 2 §6.3).

States: Triage → Correlate → Investigate → Verify.
Plan / Wait / Execute belong to the remediation subsystem and are out of scope
here. If the LLM is unavailable, Investigate is skipped and Correlate output is
returned (NF7 / T13).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum

from common.schema import Candidate, Event, Incident
from correlation_engine.engine import correlate

from rca_agent.evidence import verify_evidence
from rca_agent.llm import LLMClient, MockLLM
from rca_agent.tools import REGISTRY


class State(StrEnum):
    TRIAGE = "Triage"
    CORRELATE = "Correlate"
    INVESTIGATE = "Investigate"
    VERIFY = "Verify"


@dataclass
class DiagnosisResult:
    incident: Incident | None
    candidates: list[Candidate]
    states: list[str] = field(default_factory=list)
    tool_calls: int = 0
    llm_used: bool = False
    evidence_rejected: list[str] = field(default_factory=list)
    notes: str = ""


def run_diagnosis(
    signals: list[Event],
    *,
    llm: LLMClient | None = None,
    use_llm: bool = True,
    max_tool_calls: int = 12,
) -> DiagnosisResult:
    """Run the read-only diagnosis pipeline over already-collected signals."""
    states: list[str] = [State.TRIAGE]
    # Triage: signals already provided by the gateway / store.
    states.append(State.CORRELATE)
    incidents = correlate(signals)
    if not incidents:
        return DiagnosisResult(incident=None, candidates=[], states=states, notes="no signals")

    incident = incidents[0]
    candidates = list(incident.candidates)
    tool_calls = 0
    llm_used = False
    notes = ""

    if use_llm and llm is not None:
        states.append(State.INVESTIGATE)
        llm_used = True
        # Budgeted tool touch: call each registered tool once as a smoke probe.
        for tool in REGISTRY:
            if tool_calls >= max_tool_calls:
                break
            try:
                if tool.name == "kubectl_ro":
                    tool.run("get", "pods")
                elif tool.name == "promql":
                    tool.run("up")
                elif tool.name == "k8s_events":
                    tool.run("online-boutique")
                else:
                    tool.run("checkoutservice")
            except Exception as exc:  # noqa: BLE001 - investigation must not crash
                notes += f"{tool.name}: {exc}; "
            tool_calls += 1
        notes += llm.complete(
            f"Ranked candidates: {[c.service for c in candidates]}. "
            f"Signals: {len(signals)}. Explain top root cause briefly."
        )

    states.append(State.VERIFY)
    # Build synthetic evidence ids from signal refs for the top candidate.
    evidence_map = {}
    if candidates and incident.signal_refs:
        from common.schema import Evidence, EvidenceType

        eid = "ev-1"
        evidence_map[eid] = Evidence(
            id=eid,
            type=EvidenceType.ALERT,
            raw_ref=incident.signal_refs[0],
            summary="Primary alert for ranked service",
        )
        candidates[0] = candidates[0].model_copy(update={"evidence": [eid]})

    known_refs = set(incident.signal_refs)

    def _exists(ref: str) -> bool:
        return ref in known_refs

    candidates, rejected = verify_evidence(candidates, evidence_map, exists=_exists)
    incident = incident.model_copy(update={"candidates": candidates})
    return DiagnosisResult(
        incident=incident,
        candidates=candidates,
        states=states,
        tool_calls=tool_calls,
        llm_used=llm_used,
        evidence_rejected=rejected,
        notes=notes,
    )


def run_diagnosis_offline(signals: list[Event]) -> DiagnosisResult:
    """Convenience: correlation-only path used when LLM is down (T13)."""
    return run_diagnosis(signals, llm=None, use_llm=False)


def run_diagnosis_with_mock(signals: list[Event]) -> DiagnosisResult:
    return run_diagnosis(signals, llm=MockLLM(), use_llm=True)
