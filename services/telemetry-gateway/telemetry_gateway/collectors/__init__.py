"""Collectors normalise each source into common.schema.Event."""

from __future__ import annotations

from collections.abc import Iterable

from common.schema import Event

from telemetry_gateway.collectors import alerts, k8s_events, metrics

__all__ = ["Collector", "alerts", "k8s_events", "metrics"]


class Collector:
    """Base interface for all telemetry collectors."""

    source: str = "base"

    def collect(self) -> Iterable[Event]:  # pragma: no cover - interface stub
        raise NotImplementedError
