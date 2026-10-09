"""Read-only PromQL metric query tool. TODO(S2): call Prometheus HTTP API."""

from __future__ import annotations

from rca_agent.tools.base import ReadOnlyTool


def query(expr: str, *, window_seconds: int = 300) -> list[dict]:
    """Run a read-only PromQL query and return samples. Stubbed in S1."""
    return []


tool = ReadOnlyTool(
    name="promql",
    description="Query Prometheus metrics with PromQL (read-only).",
    run=query,
)
