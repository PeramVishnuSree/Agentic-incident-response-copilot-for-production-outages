"""In-memory incident store (Sprint 2). PostgreSQL arrives in Sprint 3."""

from __future__ import annotations

from common.schema import Event


class EventStore:
    def __init__(self) -> None:
        self._events: list[Event] = []

    def add(self, event: Event) -> None:
        self._events.append(event)

    def add_many(self, events: list[Event]) -> int:
        self._events.extend(events)
        return len(events)

    def list(self, *, service: str | None = None, limit: int = 500) -> list[Event]:
        items = self._events
        if service:
            items = [e for e in items if e.service == service]
        return items[-limit:]

    def get_by_ref(self, raw_ref: str) -> Event | None:
        for e in self._events:
            if e.raw_ref == raw_ref:
                return e
        return None

    def clear(self) -> None:
        self._events.clear()


STORE = EventStore()
