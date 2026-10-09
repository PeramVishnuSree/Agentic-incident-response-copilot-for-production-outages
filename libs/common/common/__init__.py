"""Shared library for the agentic IR copilot.

Holds the canonical telemetry event schema, configuration, and (later) the
incident/audit database models. Every service imports from here so the
collectors, correlation engine, and RCA agent cannot drift apart.
"""

__all__ = ["schema", "config"]
