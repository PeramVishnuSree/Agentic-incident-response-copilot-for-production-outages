"""Read-only kubectl tool. Only get/describe/logs verbs are ever permitted.

TODO(S2): shell out to kubectl with an allowlist of read verbs, or use the
Kubernetes read API. Any attempt to use a mutating verb must raise.
"""

from __future__ import annotations

from rca_agent.tools.base import ReadOnlyTool

READ_VERBS = frozenset({"get", "describe", "logs", "top"})


def run_kubectl(verb: str, *args: str) -> str:
    """Run a read-only kubectl command. Stubbed in S1."""
    if verb not in READ_VERBS:
        raise ValueError(f"verb '{verb}' is not read-only; RCA agent cannot mutate the cluster")
    return ""


tool = ReadOnlyTool(
    name="kubectl_ro",
    description="Read-only kubectl (get/describe/logs/top only).",
    run=run_kubectl,
)
