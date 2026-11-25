from __future__ import annotations

import re
import secrets
from collections import Counter
from collections.abc import Callable
from pathlib import Path

import pandas as pd

# Ordered by preference: trace files carry a coarse "HH:MM" string in `time`
# next to exact epoch columns, so the epoch columns must win.
_TIME_COLUMNS = ("timestamp", "startTimeMillis", "startTime", "time", "ts", "datetime")
_SERVICE_COLUMNS = ("service", "service_name", "serviceName", "container_name", "svc")
_METRIC_SUFFIXES = (
    "_latency-90",
    "_latency-50",
    "_latency",
    "_diskio",
    "_workload",
    "_socket",
    "_error",
    "_cpu",
    "_mem",
)
_ALIASES = {"redis": "redis-cart"}


def to_epoch_seconds(values: pd.Series) -> pd.Series:
    """Normalise a timestamp column (s, ms, us, ns or datetime) to integer seconds."""
    if pd.api.types.is_datetime64_any_dtype(values):
        return (values.astype("int64") // 10**9).astype("Int64")
    numeric = pd.to_numeric(values, errors="coerce")
    if numeric.notna().mean() >= 0.5:
        median = float(numeric.dropna().abs().median())
        if median > 1e17:
            numeric = numeric / 1e9
        elif median > 1e14:
            numeric = numeric / 1e6
        elif median > 1e11:
            numeric = numeric / 1e3
        return numeric.floordiv(1).astype("Int64")
    sample = values.dropna().astype(str)
    if sample.empty or sample.str.len().median() < 10:
        return pd.Series(pd.NA, index=values.index, dtype="Int64")
    parsed = pd.to_datetime(values, errors="coerce", utc=True)
    return (parsed.astype("int64") // 10**9).where(parsed.notna()).astype("Int64")


def _timestamp_series(frame: pd.DataFrame) -> pd.Series:
    for name in _TIME_COLUMNS:
        if name in frame.columns:
            ts = to_epoch_seconds(frame[name])
            if ts.notna().any():
                return ts
    return pd.Series(pd.NA, index=frame.index, dtype="Int64")


def service_from_metric(name: str) -> str | None:
    for suffix in _METRIC_SUFFIXES:
        if name.endswith(suffix):
            value = name[: -len(suffix)]
            return _ALIASES.get(value, value)
    if "_" in name:
        value = name.split("_", 1)[0]
        return _ALIASES.get(value, value)
    return None


def _read_frame(directory: Path, stem: str) -> pd.DataFrame:
    for suffix in (".parquet", ".csv"):
        path = directory / f"{stem}{suffix}"
        if path.exists():
            return pd.read_parquet(path) if suffix == ".parquet" else pd.read_csv(path)
    return pd.DataFrame()


def _service_column(frame: pd.DataFrame) -> str | None:
    return next((c for c in _SERVICE_COLUMNS if c in frame.columns), None)


def _jsonable(value: object) -> object:
    if value is None or value is pd.NA:
        return None
    if isinstance(value, float) and value != value:
        return None
    return value.item() if hasattr(value, "item") else value


class RCAEvalReplay:
    """Anonymous, time-gated replay of one RCAEval case.

    The case directory, its name, the fault label and the injection time are
    internal. Callers only ever see an opaque random case id, telemetry rows
    whose timestamps are <= ``now()``, and a topology derived from pre-``now``
    traces.

    ``now_timestamp`` should come from an onset detector. When neither it nor
    ``onset_detector`` is given, the clock defaults to inject_time + 300 s and
    ``clock_source`` records that the oracle was used.
    """

    def __init__(
        self,
        case_path: str | Path,
        now_timestamp: int | None = None,
        *,
        topology: dict | None = None,
        onset_detector: Callable[[pd.DataFrame], int] | None = None,
        case_id: str | None = None,
    ):
        self._path = Path(case_path).resolve()
        if not self._path.is_dir():
            raise FileNotFoundError(self._path)
        self._frames: dict[str, pd.DataFrame] = {}
        self._known: set[str] | None = None
        if now_timestamp is not None:
            self.clock_source = "explicit"
        elif onset_detector is not None:
            now_timestamp = int(onset_detector(self._frame("metrics")))
            self.clock_source = "onset_detector"
        else:
            inject_path = self._path / "inject_time.txt"
            now_timestamp = (
                int(inject_path.read_text().strip()) + 300 if inject_path.exists() else 0
            )
            self.clock_source = "oracle_inject_time_plus_300s"
        self._now = int(now_timestamp)
        self.case_id = case_id or f"replay-{secrets.token_hex(6)}"
        self._fallback_topology = topology
        self._topology: dict | None = None

    def _frame(self, stem: str) -> pd.DataFrame:
        if stem not in self._frames:
            frame = _read_frame(self._path, stem)
            if not frame.empty:
                frame = frame.copy()
                frame["__ts"] = _timestamp_series(frame)
                frame = frame[frame["__ts"].notna()]
                column = _service_column(frame) if stem != "metrics" else None
                if column is not None:
                    frame["__service"] = frame[column].astype(str).map(self._canonical)
            self._frames[stem] = frame
        return self._frames[stem]

    def _metric_services(self) -> set[str]:
        if self._known is None:
            frame = self._frame("metrics")
            self._known = {
                service
                for column in frame.columns
                if not column.startswith("__") and column not in _TIME_COLUMNS
                if (service := service_from_metric(str(column))) is not None
            }
        return self._known

    def _canonical(self, name: str) -> str:
        name = _ALIASES.get(name, name)
        known = self._metric_services()
        if name not in known and name.endswith("service") and name[: -len("service")] in known:
            return name[: -len("service")]
        return name

    def now(self) -> int:
        return self._now

    def _window(self, frame: pd.DataFrame, start: int, end: int) -> pd.DataFrame:
        lo, hi = int(start), min(int(end), self._now)
        if frame.empty or lo > hi:
            return frame.iloc[0:0]
        return frame[(frame["__ts"] >= lo) & (frame["__ts"] <= hi)]

    def metrics(self, service: str | None, start: int, end: int, step: int = 1) -> dict:
        """Prometheus range-query shaped result (``resultType: matrix``)."""
        frame = self._window(self._frame("metrics"), start, end)
        result = []
        if not frame.empty:
            columns = [
                c
                for c in frame.columns
                if not c.startswith("__")
                and c not in _TIME_COLUMNS
                and (service is None or service_from_metric(str(c)) == service)
            ]
            frame = frame.iloc[:: max(1, int(step))]
            timestamps = [int(t) for t in frame["__ts"]]
            for column in columns:
                values = [
                    [ts, str(_jsonable(v))]
                    for ts, v in zip(timestamps, frame[column], strict=True)
                    if pd.notna(v)
                ]
                if values:
                    result.append(
                        {
                            "metric": {
                                "__name__": str(column),
                                "service": service_from_metric(str(column)),
                                "case_id": self.case_id,
                            },
                            "values": values,
                        }
                    )
        return {"status": "success", "data": {"resultType": "matrix", "result": result}}

    def _rows(
        self, stem: str, service: str | None, start: int, end: int, limit: int | None
    ) -> list[dict]:
        frame = self._window(self._frame(stem), start, end)
        if service and "__service" in frame.columns:
            frame = frame[frame["__service"] == self._canonical(service)]
        elif service:
            frame = frame.iloc[0:0]
        if limit is not None:
            frame = frame.head(max(0, int(limit)))
        hidden = set(_TIME_COLUMNS) | {"__ts", "__service"}
        output = []
        for record in frame.to_dict("records"):
            row = {"case_id": self.case_id, "timestamp": int(record["__ts"])}
            if "__service" in record:
                row["service"] = record["__service"]
            row.update({str(k): _jsonable(v) for k, v in record.items() if k not in hidden})
            output.append(row)
        return output

    def logs(
        self,
        service: str | None,
        start: int,
        end: int,
        pattern: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        if not pattern:
            return self._rows("logs", service, start, end, limit)
        rx = re.compile(pattern, re.IGNORECASE)
        rows = self._rows("logs", service, start, end, None)
        return [r for r in rows if rx.search(str(r.get("message", r)))][: max(0, int(limit))]

    def traces(self, service: str | None, start: int, end: int, limit: int = 100) -> list[dict]:
        return self._rows("traces", service, start, end, limit)

    def services(self) -> list[str]:
        return list(self.topology()["services"])

    def topology(self) -> dict:
        if self._topology is None:
            self._topology = self._build_topology()
        return {
            "services": list(self._topology["services"]),
            "edges": [dict(edge) for edge in self._topology["edges"]],
        }

    def _build_topology(self) -> dict:
        services = self._metric_services()
        traces = self._frame("traces")
        edges: list[dict] = []
        if not traces.empty and {"spanID", "parentSpanID"} <= set(traces.columns):
            seen = traces[traces["__ts"] <= self._now]
            spans = seen[["spanID", "__service"]].dropna().drop_duplicates("spanID")
            joined = (
                seen[["parentSpanID", "__service"]]
                .dropna()
                .merge(
                    spans, left_on="parentSpanID", right_on="spanID", suffixes=("_child", "_parent")
                )
            )
            joined = joined[joined["__service_child"] != joined["__service_parent"]]
            counts = Counter(
                zip(joined["__service_parent"], joined["__service_child"], strict=True)
            )
            edges = [
                {"caller": caller, "callee": callee, "calls": int(n)}
                for (caller, callee), n in sorted(counts.items())
            ]
            services |= set(seen["__service"].dropna())
        if not edges and self._fallback_topology:
            edges = [dict(e) for e in self._fallback_topology.get("edges", [])]
            services |= set(self._fallback_topology.get("services", []))
        return {"services": sorted(services), "edges": edges}
