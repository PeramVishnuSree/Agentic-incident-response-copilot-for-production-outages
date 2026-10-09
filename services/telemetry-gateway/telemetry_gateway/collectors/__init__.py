"""Collectors normalise each source into common.schema.Event.

S2 implements these against the live cluster:
  - metrics.py      Prometheus / PromQL range queries
  - logs.py         Fluent Bit -> Elasticsearch
  - events.py       Kubernetes events
  - deploys.py      Deployment / rollout history
Each collector must emit Events that pass schema validation (E2) and set
raw_ref so evidence can be traced back to the source (E6).
"""

from __future__ import annotations

from collections.abc import Iterable

from common.schema import Event


class Collector:
    """Base interface for all telemetry collectors."""

    source: str = "base"

    def collect(self) -> Iterable[Event]:  # pragma: no cover - interface stub
        raise NotImplementedError
