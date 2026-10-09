"""Read-only diagnostic tools for the RCA agent (E6).

Every tool here is strictly read-only. The agent may query metrics, logs,
events, and the cluster's read endpoints to confirm or reject candidates, but
it can never mutate state. Enforced by `ReadOnlyTool.writes = False` and a test
(tests/test_tools_readonly.py) that fails if any registered tool claims to
write.
"""

from __future__ import annotations

from rca_agent.tools import events, kubectl_ro, logs, promql
from rca_agent.tools.base import ReadOnlyTool

REGISTRY: list[ReadOnlyTool] = [
    promql.tool,
    logs.tool,
    events.tool,
    kubectl_ro.tool,
]

__all__ = ["ReadOnlyTool", "REGISTRY"]
