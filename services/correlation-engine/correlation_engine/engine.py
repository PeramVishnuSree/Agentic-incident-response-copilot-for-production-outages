"""Public correlation API used by the RCA agent and console."""

from __future__ import annotations

from pathlib import Path

from common.config import get_settings
from common.schema import Event, Incident

from correlation_engine.graph import load_dependency_graph
from correlation_engine.grouping import group_signals
from correlation_engine.ranking import rank_candidates


def correlate(
    signals: list[Event],
    *,
    dep_graph_path: str | None = None,
    window_seconds: int | None = None,
) -> list[Incident]:
    """Group signals into incidents and attach a ranked top-3 (Stage A)."""
    settings = get_settings()
    path = dep_graph_path or settings.dep_graph_path
    # Resolve relative to repo root when running from a service package.
    graph_path = Path(path)
    if not graph_path.is_file():
        # Walk up from this file to find config/dependency-graph.yaml.
        here = Path(__file__).resolve()
        for parent in here.parents:
            candidate = parent / path
            if candidate.is_file():
                graph_path = candidate
                break
    graph = load_dependency_graph(graph_path)
    window = window_seconds if window_seconds is not None else settings.window_seconds
    incidents = group_signals(signals, graph, window_seconds=window)
    for inc in incidents:
        inc.candidates = rank_candidates(inc, signals, graph)
    return incidents
