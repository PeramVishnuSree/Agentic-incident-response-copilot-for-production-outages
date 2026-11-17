"""Prometheus metric sample collector stub (E1).

Converts a PromQL instant/range sample dict into a normalised Event. Live HTTP
polling against Prometheus is wired when the cluster is up; unit tests use
synthetic samples so CI stays offline.
"""

from __future__ import annotations

from typing import Any

from common.schema import Event, SignalType

from telemetry_gateway.normalizer import normalize


def from_prom_sample(sample: dict[str, Any], *, namespace: str = "online-boutique") -> Event:
    metric = sample.get("metric", {})
    service = metric.get("service") or metric.get("app") or metric.get("job") or "unknown"
    name = metric.get("__name__", "metric")
    ts = sample.get("timestamp") or sample.get("time")
    value = sample.get("value")
    severity = "warning" if isinstance(value, (int, float)) and float(value) > 0 else "info"
    return normalize(
        signal_type=SignalType.METRIC,
        service=service,
        namespace=metric.get("namespace", namespace),
        pod=metric.get("pod"),
        severity=severity,
        time=ts,
        raw_ref=f"prom://{name}/{service}/{ts}",
        labels={"metric": name, "value": str(value)},
    )
