"""Shared helpers for RCAEval experiments (RE1 / RE2 / RE3)."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = REPO_ROOT / "eval" / "artifacts" / "rcaeval"
DEFAULT_DATA_ROOTS = [
    Path(os.environ["RCAEVAL_DIR"]) if os.environ.get("RCAEVAL_DIR") else None,
    REPO_ROOT.parent / "datasets" / "RCAEval",
    REPO_ROOT / "datasets" / "RCAEval",
    Path.home() / "Desktop" / "Masters RCA" / "datasets" / "RCAEval",
]

ALL_SUITES = [
    "re1ob",
    "re1ss",
    "re1tt",
    "re2ob",
    "re2ss",
    "re2tt",
    "re3ob",
    "re3ss",
    "re3tt",
]

# Longest-first metric suffixes used across RCAEval systems.
_METRIC_SUFFIXES = [
    "_latency-90",
    "_latency-50",
    "_latency",
    "_diskio",
    "_workload",
    "_socket",
    "_error",
    "_cpu",
    "_mem",
]

_CASE_RE = re.compile(r"^(re[123](?:ob|ss|tt))_(.+)_(cpu|mem|disk|delay|loss|socket|f[1-5])_(\d+)$")


@dataclass(frozen=True)
class Case:
    path: Path
    suite: str
    service: str
    fault: str
    rep: str

    @property
    def name(self) -> str:
        return self.path.name


def find_data_root() -> Path:
    for root in DEFAULT_DATA_ROOTS:
        if (
            root
            and root.is_dir()
            and (
                any(root.glob("re*_*"))
                or (root / "RE2-OB").is_dir()
                or (root / "RE2" / "RE2-OB").is_dir()
            )
        ):
            if (root / "RE2" / "RE2-OB").is_dir():
                return root / "RE2"
            return root
    raise FileNotFoundError(
        "RCAEval data not found. Set RCAEVAL_DIR or place data under ../datasets/RCAEval"
    )


def parse_case(path: Path) -> Case | None:
    m = _CASE_RE.match(path.name)
    if m:
        return Case(
            path=path, suite=m.group(1), service=m.group(2), fault=m.group(3), rep=m.group(4)
        )
    if path.parent.parent.name.startswith("RE"):
        suite = path.parent.parent.name.lower().replace("-", "")
        if suite not in ALL_SUITES:
            return None
        try:
            service, fault = path.parent.name.rsplit("_", 1)
        except ValueError:
            return None
        return Case(path=path, suite=suite, service=service, fault=fault, rep=path.name)
    return None


def list_cases(root: Path | None = None, suite: str = "re2ob") -> list[Case]:
    root = root or find_data_root()
    cases = []
    candidates = list(root.iterdir())
    dataset_dir = root / suite.upper().replace("OB", "-OB").replace("SS", "-SS").replace(
        "TT", "-TT"
    )
    if dataset_dir.is_dir():
        for child in dataset_dir.iterdir():
            if not child.is_dir():
                continue
            if _CASE_RE.match(child.name):
                candidates.append(child)
            else:
                candidates.extend(case for case in child.iterdir() if case.is_dir())
    for p in sorted(candidates):
        if not p.is_dir():
            continue
        c = parse_case(p)
        if (
            c
            and c.suite == suite
            and (p.name.isdigit() or _CASE_RE.match(p.name))
            and any(
                (p / filename).exists()
                for filename in ("metrics.parquet", "metrics.csv", "simple_metrics.csv")
            )
        ):
            cases.append(c)
    unique: dict[tuple[str, str, str], Case] = {}
    for c in cases:
        unique.setdefault((c.service, c.fault, c.rep), c)
    return list(unique.values())


def load_metrics(case: Case) -> pd.DataFrame:
    for filename in ("metrics.parquet", "metrics.csv", "simple_metrics.csv"):
        path = case.path / filename
        if path.exists():
            return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    raise FileNotFoundError(f"No metrics file in {case.path}")


def load_logs(case: Case) -> pd.DataFrame:
    for filename in ("logs.parquet", "logs.csv", "logts.csv"):
        path = case.path / filename
        if path.exists():
            return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    return pd.DataFrame()


def load_traces(case: Case) -> pd.DataFrame:
    for filename in ("traces.parquet", "traces.csv", "tracets_lat.csv"):
        path = case.path / filename
        if path.exists():
            return pd.read_parquet(path) if path.suffix == ".parquet" else pd.read_csv(path)
    return pd.DataFrame()


def inject_time(case: Case) -> int:
    return int((case.path / "inject_time.txt").read_text().strip())


def metric_to_service(metric: str) -> str | None:
    if metric == "time":
        return None
    for suf in _METRIC_SUFFIXES:
        if metric.endswith(suf):
            svc = metric[: -len(suf)]
            return "redis-cart" if svc == "redis" else svc
    if "_" in metric:
        svc = metric.split("_", 1)[0]
        return "redis-cart" if svc == "redis" else svc
    return None


def services_from_metrics(metrics: pd.DataFrame) -> list[str]:
    found = {metric_to_service(c) for c in metrics.columns}
    return sorted(s for s in found if s)


def ranks_to_services(ranks: list[str]) -> list[str]:
    out: list[str] = []
    for r in ranks:
        svc = metric_to_service(r)
        if svc and svc not in out:
            out.append(svc)
    return out


def ac_at_k(pred_services: list[str], truth: str, k: int) -> float:
    # Normalize redis naming
    truth_n = "redis-cart" if truth == "redis" else truth
    preds = ["redis-cart" if p == "redis" else p for p in pred_services]
    return 1.0 if truth_n in preds[:k] else 0.0


def avg_at_5(pred_services: list[str], truth: str) -> float:
    return sum(ac_at_k(pred_services, truth, k) for k in range(1, 6)) / 5.0


def save_json(path: Path, obj: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str))
