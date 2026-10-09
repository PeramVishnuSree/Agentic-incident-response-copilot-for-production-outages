"""Read-only log search tool. TODO(S2): query Elasticsearch / Loki."""

from __future__ import annotations

from rca_agent.tools.base import ReadOnlyTool


def search(query_string: str, *, service: str | None = None, limit: int = 100) -> list[dict]:
    """Search stored logs (read-only). Stubbed in S1."""
    return []


tool = ReadOnlyTool(
    name="logs",
    description="Search service logs (read-only).",
    run=search,
)
