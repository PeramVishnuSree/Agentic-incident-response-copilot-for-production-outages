"""Canonical telemetry event schema (requirement E2).

All collectors normalise metrics, logs, Kubernetes events, deployment history,
and alerts into this single schema before anything is stored or correlated.
Fields: time, service, pod, namespace, type, severity, and a reference back to
the raw data so every downstream claim can be traced to its source.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class SignalType(StrEnum):
    METRIC = "metric"
    LOG = "log"
    K8S_EVENT = "k8s_event"
    DEPLOYMENT = "deployment"
    ALERT = "alert"


class Severity(StrEnum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Event(BaseModel):
    """One normalised telemetry signal."""

    time: datetime = Field(..., description="Event timestamp (UTC).")
    service: str = Field(..., description="Logical service name, e.g. 'checkoutservice'.")
    pod: str | None = Field(None, description="Pod name if applicable.")
    namespace: str = Field(..., description="Kubernetes namespace.")
    type: SignalType = Field(..., description="Signal category.")
    severity: Severity = Field(Severity.INFO, description="Normalised severity.")
    raw_ref: str = Field(
        ...,
        description="Reference (URI / store id) to the raw signal for evidence checks.",
    )
    labels: dict[str, str] = Field(default_factory=dict, description="Extra key/value labels.")

    model_config = {"frozen": True}
