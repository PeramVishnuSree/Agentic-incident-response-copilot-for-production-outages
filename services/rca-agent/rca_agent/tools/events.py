"""Read-only Kubernetes event lookup tool. TODO(S2): query the event store."""

from __future__ import annotations

from rca_agent.tools.base import ReadOnlyTool


def list_events(namespace: str, *, since_seconds: int = 600) -> list[dict]:
    """List Kubernetes events in a namespace (read-only). Stubbed in S1."""
    return []


tool = ReadOnlyTool(
    name="k8s_events",
    description="List Kubernetes events (read-only).",
    run=list_events,
)
