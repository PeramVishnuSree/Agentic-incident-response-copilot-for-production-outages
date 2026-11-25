"""Read-only telemetry tools exposed to the RCA agent.

Every tool goes through a TelemetrySource (the TAL), so the agent can never see
data after ``source.now()``. Results are summarised rather than returned raw:
a five-minute metric window is ~20k rows, far beyond a small model's context.
"""

from __future__ import annotations

import re
import statistics
from collections import Counter, defaultdict
from typing import Any

MAX_WINDOW_SECONDS = 3600
_TIME_PROPS = {
    "start": {
        "type": "integer",
        "description": "Window start, unix seconds. Negative values mean seconds before now.",
    },
    "end": {
        "type": "integer",
        "description": "Window end, unix seconds (clipped to now). Negative = seconds before now.",
    },
}


def schemas() -> list[dict]:
    return [
        {
            "type": "function",
            "function": {
                "name": "get_metrics",
                "description": (
                    "Compare each metric in [start, end] with the equally long window just "
                    "before it. Omit service to get the most-changed metrics across all "
                    "services; give a service to see all of its metrics."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {"service": {"type": "string"}, **_TIME_PROPS},
                    "required": ["start", "end"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "search_logs",
                "description": (
                    "Count log lines in [start, end] (optionally for one service and matching "
                    "a regex) versus the window just before, with the most frequent messages."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "service": {"type": "string"},
                        "pattern": {"type": "string", "description": "Case-insensitive regex"},
                        **_TIME_PROPS,
                    },
                    "required": ["start", "end"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_topology",
                "description": "Read the service list and caller->callee dependency edges.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
    ]


def _window(source: Any, arguments: dict) -> tuple[int, int]:
    now = int(source.now())
    try:
        start, end = int(arguments["start"]), int(arguments["end"])
    except KeyError as exc:
        raise ValueError(f"missing argument: {exc.args[0]}") from exc
    start = now + start if start <= 0 else start
    end = now + end if end <= 0 else end
    end = min(end, now)
    if start >= end:
        raise ValueError(f"empty window: start={start} end={end} now={now}")
    if end - start > MAX_WINDOW_SECONDS:
        start = end - MAX_WINDOW_SECONDS
    return start, end


def _known_service(source: Any, service: str | None) -> str | None:
    if not service:
        return None
    services = source.topology().get("services", [])
    if services and service not in services:
        raise ValueError(f"unknown service {service!r}; known services: {', '.join(services)}")
    return service


def _series(matrix: dict) -> dict[str, list[float]]:
    out: dict[str, list[float]] = defaultdict(list)
    for series in matrix.get("data", {}).get("result", []):
        name = str(series["metric"]["__name__"])
        for _, value in series["values"]:
            try:
                out[name].append(float(value))
            except (TypeError, ValueError):
                continue
    return out


def get_metrics(source: Any, arguments: dict, top_k: int = 12) -> dict:
    start, end = _window(source, arguments)
    service = _known_service(source, arguments.get("service"))
    span = end - start
    recent = _series(source.metrics(service, start, end))
    baseline = _series(source.metrics(service, start - span, start - 1))
    changes = []
    for metric, values in recent.items():
        before = baseline.get(metric, [])
        if len(before) < 3 or not values:
            continue
        mean_before = statistics.fmean(before)
        mean_now = statistics.fmean(values)
        # A constant baseline has zero spread; without a floor a 23 -> 23.1
        # change scores like a real outage (the same flaw as BARO's zero IQR).
        scale = max(statistics.pstdev(before), 0.01 * abs(mean_before), 1e-6)
        z = (mean_now - mean_before) / scale
        changes.append(
            {
                "metric": metric,
                "baseline_mean": round(mean_before, 4),
                "recent_mean": round(mean_now, 4),
                "recent_max": round(max(values), 4),
                "z_score": round(max(min(z, 1e6), -1e6), 2),
            }
        )
    changes.sort(key=lambda item: abs(item["z_score"]), reverse=True)
    return {
        "window": {"start": start, "end": end, "baseline_start": start - span},
        "service": service or "*",
        "metrics": changes if service else changes[:top_k],
        "n_metrics_compared": len(changes),
    }


def search_logs(source: Any, arguments: dict, top_k: int = 8) -> dict:
    start, end = _window(source, arguments)
    service = _known_service(source, arguments.get("service"))
    pattern = arguments.get("pattern") or None
    if pattern:
        try:
            re.compile(pattern)
        except re.error as exc:
            raise ValueError(f"invalid regex: {exc}") from exc
    span = end - start
    limit = 200_000
    recent = source.logs(service, start, end, pattern=pattern, limit=limit)
    before = source.logs(service, start - span, start - 1, pattern=pattern, limit=limit)
    by_service_now = Counter(str(r.get("service", "?")) for r in recent)
    by_service_before = Counter(str(r.get("service", "?")) for r in before)
    messages = Counter(
        re.sub(r"[0-9a-f-]{8,}|\d+", "<n>", str(r.get("message", "")))[:160] for r in recent
    )
    return {
        "window": {"start": start, "end": end, "baseline_start": start - span},
        "service": service or "*",
        "pattern": pattern,
        "count": len(recent),
        "baseline_count": len(before),
        "by_service": {
            s: {"count": by_service_now[s], "baseline_count": by_service_before.get(s, 0)}
            for s in sorted(set(by_service_now) | set(by_service_before))
        },
        "top_messages": [{"message": m, "count": n} for m, n in messages.most_common(top_k)],
    }


def get_topology(source: Any, arguments: dict) -> dict:
    return source.topology()


TOOLS = {"get_metrics": get_metrics, "search_logs": search_logs, "get_topology": get_topology}


def dispatch(source: Any, name: str, arguments: dict) -> Any:
    if name not in TOOLS:
        raise ValueError(f"unknown telemetry tool: {name}")
    if not isinstance(arguments, dict):
        raise ValueError("tool arguments must be a JSON object")
    return TOOLS[name](source, arguments)
