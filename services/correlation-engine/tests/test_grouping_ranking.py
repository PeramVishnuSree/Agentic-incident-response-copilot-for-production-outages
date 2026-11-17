"""Correlation grouping + ranking tests (E3, E4, E5, T6, T7, T13-ready)."""

from datetime import UTC, datetime, timedelta

from common.schema import Event, Severity, SignalType
from correlation_engine.engine import correlate
from correlation_engine.graph import load_dependency_graph


def _ev(
    service: str,
    seconds: int,
    *,
    severity: Severity = Severity.ERROR,
    ref: str | None = None,
) -> Event:
    return Event(
        time=datetime(2026, 11, 3, 12, 0, 0, tzinfo=UTC) + timedelta(seconds=seconds),
        service=service,
        pod=f"{service}-pod",
        namespace="online-boutique",
        type=SignalType.ALERT,
        severity=severity,
        raw_ref=ref or f"alert://{service}/{seconds}",
    )


def test_dependency_graph_covers_online_boutique_core():
    g = load_dependency_graph("config/dependency-graph.yaml")
    assert "frontend" in g
    assert g.has_edge("frontend", "checkoutservice")
    assert g.has_edge("checkoutservice", "cartservice")


def test_cascade_groups_into_one_incident():
    # checkout fails first; frontend/cart light up within the window → one incident
    signals = [
        _ev("checkoutservice", 0, severity=Severity.CRITICAL),
        _ev("frontend", 20, severity=Severity.ERROR),
        _ev("cartservice", 40, severity=Severity.WARNING),
    ]
    incidents = correlate(signals, window_seconds=120)
    assert len(incidents) == 1
    assert set(incidents[0].services) == {"checkoutservice", "frontend", "cartservice"}


def test_ranking_prefers_earlier_upstream_root():
    signals = [
        _ev("checkoutservice", 0, severity=Severity.CRITICAL),
        _ev("frontend", 30, severity=Severity.ERROR),
        _ev("cartservice", 45, severity=Severity.WARNING),
    ]
    incidents = correlate(signals, window_seconds=120)
    assert len(incidents[0].candidates) == 3
    top = incidents[0].candidates[0]
    assert top.service == "checkoutservice"
    assert top.rank == 1


def test_far_apart_unrelated_services_stay_separate():
    signals = [
        _ev("adservice", 0),
        _ev("paymentservice", 600),  # 10 minutes later, outside default window
    ]
    incidents = correlate(signals, window_seconds=120)
    assert len(incidents) == 2
