"""Kubernetes event collector (E1) — converts event dicts to schema Events."""

from __future__ import annotations

from typing import Any

from common.schema import Event, SignalType

from telemetry_gateway.normalizer import normalize


def from_k8s_event(obj: dict[str, Any], *, namespace: str = "online-boutique") -> Event:
    meta = obj.get("metadata", {})
    involved = obj.get("involvedObject", {})
    reason = obj.get("reason", "Unknown")
    service = (
        involved.get("name", "").rsplit("-", 2)[0]
        if involved.get("kind") == "Pod"
        else involved.get("name", "unknown")
    )
    # Strip replica-set hash suffixes when present: checkoutservice-7f9c-x2k -> checkoutservice
    if "-" in service:
        service = service.split("-")[0] if service.count("-") >= 1 else service
    # Prefer explicit app label if caller provided it
    labels = meta.get("labels") or {}
    service = labels.get("app") or labels.get("service") or service or "unknown"
    severity = "warning" if obj.get("type", "Normal") == "Warning" else "info"
    if reason.lower() in {"killing", "backoff", "unhealthy", "failed"}:
        severity = "error"
    uid = meta.get("uid") or meta.get("resourceVersion") or reason
    return normalize(
        signal_type=SignalType.K8S_EVENT,
        service=service,
        namespace=meta.get("namespace", namespace),
        pod=involved.get("name") if involved.get("kind") == "Pod" else None,
        severity=severity,
        time=obj.get("lastTimestamp") or obj.get("eventTime") or meta.get("creationTimestamp"),
        raw_ref=f"k8s-event://{namespace}/{uid}",
        labels={"reason": reason, "message": str(obj.get("message", ""))[:200]},
    )
