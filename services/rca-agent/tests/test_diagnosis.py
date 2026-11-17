"""RCA diagnosis pipeline tests (E5, E6, NF7, T7, T8, T13)."""

from datetime import UTC, datetime, timedelta

from common.schema import Candidate, Event, Evidence, EvidenceType, Severity, SignalType
from rca_agent.evidence import verify_evidence
from rca_agent.graph import run_diagnosis_offline, run_diagnosis_with_mock


def _ev(service: str, seconds: int, severity: Severity = Severity.ERROR) -> Event:
    return Event(
        time=datetime(2026, 11, 3, 12, 0, 0, tzinfo=UTC) + timedelta(seconds=seconds),
        service=service,
        pod=f"{service}-x",
        namespace="online-boutique",
        type=SignalType.ALERT,
        severity=severity,
        raw_ref=f"alert://{service}/{seconds}",
    )


def test_offline_correlation_returns_top3_without_llm():
    signals = [
        _ev("checkoutservice", 0, Severity.CRITICAL),
        _ev("frontend", 15),
        _ev("cartservice", 25, Severity.WARNING),
    ]
    result = run_diagnosis_offline(signals)
    assert result.llm_used is False
    assert "Correlate" in result.states
    assert "Investigate" not in result.states
    assert len(result.candidates) == 3
    assert result.candidates[0].service == "checkoutservice"


def test_mock_llm_path_records_investigate_state():
    signals = [
        _ev("checkoutservice", 0, Severity.CRITICAL),
        _ev("frontend", 10),
        _ev("cartservice", 20),
    ]
    result = run_diagnosis_with_mock(signals)
    assert result.llm_used is True
    assert "Investigate" in result.states
    assert result.tool_calls >= 1


def test_evidence_verifier_rejects_missing_raw_ref():
    cand = Candidate(service="checkoutservice", score=0.9, rank=1, evidence=["ev-bad"])
    evidence = {
        "ev-bad": Evidence(
            id="ev-bad",
            type=EvidenceType.ALERT,
            raw_ref="missing://ref",
            summary="bogus",
        )
    }
    cleaned, rejected = verify_evidence([cand], evidence, exists=lambda _r: False)
    assert rejected == ["ev-bad"]
    assert cleaned[0].evidence == []
