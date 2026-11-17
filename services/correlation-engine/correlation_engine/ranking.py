"""Deterministic candidate ranking (requirement E5). No LLM required."""

from __future__ import annotations

from datetime import datetime

import networkx as nx
from common.schema import Candidate, Event, Incident, Severity

from correlation_engine.graph import upstreamness
from correlation_engine.grouping import earliest_onset

_SEVERITY_WEIGHT = {
    Severity.INFO: 0.1,
    Severity.WARNING: 0.4,
    Severity.ERROR: 0.7,
    Severity.CRITICAL: 1.0,
}

W1, W2, W3 = 0.45, 0.30, 0.25  # severity, upstreamness, precedence


def _severity(service: str, signals: list[Event]) -> float:
    vals = [_SEVERITY_WEIGHT.get(e.severity, 0.1) for e in signals if e.service == service]
    return max(vals) if vals else 0.0


def _precedence(service: str, signals: list[Event], started_at: datetime) -> float:
    onset = earliest_onset(signals, service)
    if onset is None:
        return 0.0
    # Earlier onset -> higher score. Cap at 300s for normalisation.
    delta = max(0.0, (onset - started_at).total_seconds())
    return max(0.0, 1.0 - (delta / 300.0))


def rank_candidates(
    incident: Incident,
    signals: list[Event],
    graph: nx.DiGraph,
    *,
    top_k: int = 3,
) -> list[Candidate]:
    """Score each service in the incident; return top-k ranked candidates."""
    related = [e for e in signals if e.raw_ref in set(incident.signal_refs)]
    scores: dict[str, float] = {}
    for svc in incident.services:
        scores[svc] = (
            W1 * _severity(svc, related)
            + W2 * upstreamness(svc, graph)
            + W3 * _precedence(svc, related, incident.started_at)
        )
    ordered = sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))[:top_k]
    return [
        Candidate(service=svc, score=round(score, 4), rank=i + 1, confidence=round(score, 4))
        for i, (svc, score) in enumerate(ordered)
    ]
