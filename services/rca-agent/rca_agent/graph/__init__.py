"""LangGraph orchestration for the RCA agent (ReAct-style reason/act loop).

S2 builds the stateful graph: take ranked candidates from the correlation
engine, let the agent inspect each with read-only tools, and emit candidates
with cited evidence. S1 only defines the node contract.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class RCAState:
    incident_id: str
    candidates: list[dict] = field(default_factory=list)
    evidence: list[dict] = field(default_factory=list)


def build_graph():  # pragma: no cover - wired up in S2
    """Return the compiled LangGraph app. Not implemented in S1."""
    raise NotImplementedError("RCA graph is implemented in S2")
