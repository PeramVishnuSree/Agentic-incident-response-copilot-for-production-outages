"""Telemetry gateway API — health, ingest, alert webhook, event query (E1/E2)."""

from __future__ import annotations

from typing import Any

from common.schema import Event
from fastapi import FastAPI

from telemetry_gateway.collectors.alerts import from_alertmanager_payload
from telemetry_gateway.store import STORE

app = FastAPI(title="Telemetry Gateway", version="0.2.0")


@app.get("/healthz")
def healthz() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest")
def ingest(event: Event) -> dict[str, str]:
    """Accept one normalised event and store it."""
    STORE.add(event)
    return {"accepted": event.raw_ref}


@app.post("/ingest/batch")
def ingest_batch(events: list[Event]) -> dict[str, int]:
    n = STORE.add_many(events)
    return {"accepted": n}


@app.post("/webhook/alertmanager")
def alertmanager_webhook(payload: dict[str, Any]) -> dict[str, int]:
    """Alertmanager push path — normalise and store alerts."""
    events = from_alertmanager_payload(payload)
    n = STORE.add_many(events)
    return {"accepted": n}


@app.get("/events")
def query_events(service: str | None = None, limit: int = 500) -> list[Event]:
    return STORE.list(service=service, limit=limit)


@app.delete("/events")
def clear_events() -> dict[str, str]:
    STORE.clear()
    return {"status": "cleared"}
