"""Normalise raw collector payloads into common.schema.Event (E2)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from common.schema import Event, Severity, SignalType


def _parse_time(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=UTC)
    if isinstance(value, str):
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return datetime.now(UTC)


def _severity(raw: str | None) -> Severity:
    if not raw:
        return Severity.INFO
    key = raw.lower()
    for s in Severity:
        if s.value == key:
            return s
    if key in {"fatal", "crit", "critical"}:
        return Severity.CRITICAL
    if key in {"err", "error", "failed"}:
        return Severity.ERROR
    if key in {"warn", "warning"}:
        return Severity.WARNING
    return Severity.INFO


def normalize(
    *,
    signal_type: SignalType | str,
    service: str,
    namespace: str,
    raw_ref: str,
    time: Any = None,
    pod: str | None = None,
    severity: str | None = None,
    labels: dict[str, str] | None = None,
) -> Event:
    st = signal_type if isinstance(signal_type, SignalType) else SignalType(signal_type)
    return Event(
        time=_parse_time(time),
        service=service,
        pod=pod,
        namespace=namespace,
        type=st,
        severity=_severity(severity),
        raw_ref=raw_ref,
        labels=labels or {},
    )
