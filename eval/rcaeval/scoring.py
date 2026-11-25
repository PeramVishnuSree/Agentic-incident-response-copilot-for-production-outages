"""Ranking metrics with bootstrap confidence intervals (shared interface).

Implements the signatures agreed in the Phase 0 roadmap::

    score(preds, truth) -> table          # AC@1/3/5, Avg@5 + 95% CIs, per fault
    paired_bootstrap(scores_a, scores_b)  # "does A really beat B?"

AC@k and Avg@5 follow RCAEval's Evaluator: AC@k is the share of cases whose
true service is in the top k, and Avg@5 is the mean of AC@1..AC@5.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

import numpy as np
import pandas as pd

METRICS = ("AC@1", "AC@3", "AC@5", "Avg@5")


def case_hits(ranked: Sequence[str], truth: str) -> dict[str, float]:
    """Per-case AC@1/3/5 and Avg@5 for one ranking (duplicates ignored)."""
    seen: list[str] = []
    for item in ranked:
        if item not in seen:
            seen.append(item)
    position = seen.index(truth) + 1 if truth in seen else None
    hit = {k: float(position is not None and position <= k) for k in range(1, 6)}
    return {"AC@1": hit[1], "AC@3": hit[3], "AC@5": hit[5], "Avg@5": sum(hit.values()) / 5}


def _fault_of(case: str) -> str:
    parts = case.split("_")
    return parts[-2] if len(parts) >= 3 else "all"


def _bootstrap_ci(values: np.ndarray, n_boot: int, rng: np.random.Generator) -> tuple[float, float]:
    if len(values) < 2:
        return float(values.mean()), float(values.mean())
    means = rng.choice(values, size=(n_boot, len(values)), replace=True).mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(lo), float(hi)


def score(
    preds: Mapping[str, Sequence[str]],
    truth: Mapping[str, str],
    *,
    faults: Mapping[str, str] | None = None,
    n_boot: int = 2000,
    seed: int = 0,
) -> pd.DataFrame:
    """One row for all cases plus one per fault; mean and 95% bootstrap CI per metric.

    Cases missing from ``preds`` count as misses. The fault of a case is read
    from ``faults`` or, by default, from ids shaped ``<service>_<fault>_<n>``.
    """
    rng = np.random.default_rng(seed)
    rows = []
    for case, answer in truth.items():
        hits = case_hits(preds.get(case, []), answer)
        fault = (faults or {}).get(case) or _fault_of(case)
        rows.append({"case": case, "fault": fault, **hits})
    per_case = pd.DataFrame(rows)
    groups = [("all", per_case)] + [
        (fault, group) for fault, group in sorted(per_case.groupby("fault"), key=lambda g: g[0])
    ]
    table = []
    for name, group in groups:
        record: dict[str, object] = {"fault": name, "n": len(group)}
        for metric in METRICS:
            values = group[metric].to_numpy(dtype=float)
            lo, hi = _bootstrap_ci(values, n_boot, rng)
            record[metric] = float(values.mean())
            record[f"{metric}_lo"] = lo
            record[f"{metric}_hi"] = hi
        table.append(record)
    return pd.DataFrame(table).set_index("fault")


def paired_bootstrap(
    scores_a: Sequence[float], scores_b: Sequence[float], *, n_boot: int = 10000, seed: int = 0
) -> tuple[float, tuple[float, float]]:
    """Mean difference A - B over the same cases, with a 95% paired bootstrap CI."""
    a = np.asarray(scores_a, dtype=float)
    b = np.asarray(scores_b, dtype=float)
    if a.shape != b.shape:
        raise ValueError("paired_bootstrap needs scores for the same cases in the same order")
    diff = a - b
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(diff), size=(n_boot, len(diff)))
    means = diff[idx].mean(axis=1)
    lo, hi = np.percentile(means, [2.5, 97.5])
    return float(diff.mean()), (float(lo), float(hi))
