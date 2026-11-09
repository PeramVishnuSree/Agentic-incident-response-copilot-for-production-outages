"""Alertmanager webhook collector — push path for alerts (E1)."""

from __future__ import annotations

from typing import Any

from common.schema import Event, SignalType

from telemetry_gateway.normalizer import normalize


def from_alertmanager_payload(
    payload: dict[str, Any],
    *,
    namespace: str = "online-boutique",
) -> list[Event]:
    """Convert an Alertmanager webhook body into normalised Events."""
    events: list[Event] = []
    for i, alert in enumerate(payload.get("alerts", [])):
        labels = alert.get("labels", {})
        annotations = alert.get("annotations", {})
        service = (
            labels.get("service") or labels.get("job") or labels.get("app") or "unknown"
        )
        severity = labels.get("severity", "warning")
        alertname = labels.get("alertname", f"alert-{i}")
        starts = alert.get("startsAt") or alert.get("starts_at")
        events.append(
            normalize(
                signal_type=SignalType.ALERT,
                service=service,
                namespace=labels.get("namespace", namespace),
                pod=labels.get("pod"),
                severity=severity,
                time=starts,
                raw_ref=f"am://{alertname}/{service}/{starts or i}",
                labels={
                    "alertname": alertname,
                    "summary": annotations.get("summary", ""),
                },
            )
        )
    return events
