"""Sliding-window + dependency-graph incident grouping (requirement E4)."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta

import networkx as nx
from common.schema import Event, Incident

from correlation_engine.graph import connected_in_undirected


class _UnionFind:
    def __init__(self) -> None:
        self.parent: dict[str, str] = {}

    def find(self, x: str) -> str:
        self.parent.setdefault(x, x)
        if self.parent[x] != x:
            self.parent[x] = self.find(self.parent[x])
        return self.parent[x]

    def union(self, a: str, b: str) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.parent[rb] = ra


def group_signals(
    signals: list[Event],
    graph: nx.DiGraph,
    *,
    window_seconds: int = 120,
) -> list[Incident]:
    """Merge signals in the same time window that are dependency-connected.

    A cascade from one fault becomes one incident (acceptance test T6 / E4).
    """
    if not signals:
        return []

    ordered = sorted(signals, key=lambda e: e.time)
    uf = _UnionFind()
    for i, a in enumerate(ordered):
        uf.find(a.raw_ref)
        window_end = a.time + timedelta(seconds=window_seconds)
        for b in ordered[i + 1 :]:
            if b.time > window_end:
                break
            if connected_in_undirected(a.service, b.service, graph):
                uf.union(a.raw_ref, b.raw_ref)

    buckets: dict[str, list[Event]] = defaultdict(list)
    for ev in ordered:
        buckets[uf.find(ev.raw_ref)].append(ev)

    incidents: list[Incident] = []
    for idx, (_root, members) in enumerate(sorted(buckets.items(), key=lambda x: x[1][0].time)):
        services = sorted({m.service for m in members})
        started = min(m.time for m in members)
        incidents.append(
            Incident(
                id=f"inc-{idx + 1:04d}",
                started_at=started,
                services=services,
                signal_refs=[m.raw_ref for m in members],
            )
        )
    return incidents


def earliest_onset(signals: list[Event], service: str) -> datetime | None:
    times = [e.time for e in signals if e.service == service]
    return min(times) if times else None
