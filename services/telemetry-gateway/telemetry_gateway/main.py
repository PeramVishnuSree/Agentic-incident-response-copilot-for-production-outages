"""Telemetry gateway API (S1 skeleton).

Exposes a health check plus ingest/query stubs. Real collector wiring and the
PostgreSQL-backed incident store arrive in S2/S3.
"""

from __future__ import annotations

from common.schema import Event
from fastapi import FastAPI

app = FastAPI(title="Telemetry Gateway", version="0.0.1")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest")
def ingest(event: Event) -> dict[str, str]:
    """Accept one normalised event. TODO(S2): persist to the incident store."""
    # Placeholder: validation happens via the Event model.
    return {"accepted": event.raw_ref}


@app.get("/events")
def query_events() -> list[Event]:
    """Query stored events. TODO(S2): back with PostgreSQL."""
    return []
