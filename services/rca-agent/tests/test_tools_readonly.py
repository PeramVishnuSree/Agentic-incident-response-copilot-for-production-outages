"""Safety invariant: every registered RCA tool is read-only (E6, NFR: safety).

This is the structural guard behind the project's core safety property -- no
agent tool call can directly change the cluster. If anyone adds a writing tool
to the RCA registry, this test fails.
"""

import pytest
from rca_agent.tools import REGISTRY
from rca_agent.tools.kubectl_ro import run_kubectl


def test_all_registered_tools_are_read_only():
    assert REGISTRY, "tool registry should not be empty"
    offenders = [t.name for t in REGISTRY if t.writes]
    assert not offenders, f"writing tools are forbidden in the RCA agent: {offenders}"


def test_kubectl_rejects_mutating_verbs():
    with pytest.raises(ValueError):
        run_kubectl("delete", "pod", "checkoutservice-123")
