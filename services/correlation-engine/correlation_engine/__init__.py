"""Correlation engine (Patrini).

Groups related signals into one incident using time windows and the service
dependency graph, then ranks candidate root causes deterministically — before
any LLM is involved — so a result is always available even if the model is
down (NFR: resilience).
"""

from correlation_engine.engine import correlate
from correlation_engine.graph import load_dependency_graph

__all__ = ["correlate", "load_dependency_graph"]
