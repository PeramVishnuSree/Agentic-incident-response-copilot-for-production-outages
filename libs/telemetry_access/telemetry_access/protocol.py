from __future__ import annotations

from typing import Protocol


class TelemetrySource(Protocol):
    """The only telemetry surface an RCA investigator is allowed to use."""

    def now(self) -> int: ...

    def metrics(self, service: str | None, start: int, end: int, step: int = 1) -> dict:
        """Prometheus range-query shape: {"data": {"resultType": "matrix", "result": [
        {"metric": {"__name__": ..., "service": ...}, "values": [[ts, "value"], ...]}]}}."""
        ...

    def logs(
        self,
        service: str | None,
        start: int,
        end: int,
        pattern: str | None = None,
        limit: int = 100,
    ) -> list[dict]: ...

    def traces(self, service: str | None, start: int, end: int, limit: int = 100) -> list[dict]: ...

    def topology(self) -> dict: ...
