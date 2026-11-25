"""N1 step 3-4: why did our BARO score AC@1 0.30 on RE2-OB?

Runs RCAEval's BARO on the same 90 RE2-OB cases under controlled preprocessing
variants, changing one thing at a time from our original harness towards the
official ``main.py`` pipeline, and counts how often a redis metric is ranked
first. The official ``main.py`` run (archived under official_runs/baro) is
counted the same way.

    uv run python -m eval.rcaeval.redis_hypothesis
"""

from __future__ import annotations

import json
from collections import Counter

import numpy as np
import pandas as pd
from RCAEval.e2e import baro
from tqdm import tqdm

from eval.rcaeval.common import ARTIFACTS, inject_time, list_cases, load_metrics, save_json

OFFICIAL = ARTIFACTS / "official_runs"
WINDOW_ROWS = 600  # main.py: length=20 min -> 20*60//2 rows on each side


def _drop_constant(data: pd.DataFrame) -> pd.DataFrame:
    keep = ["time"] + [c for c in data.columns if c != "time" and data[c].nunique() > 1]
    return data[keep]


def _official_clean(data: pd.DataFrame) -> pd.DataFrame:
    data = data.loc[:, ~data.columns.str.endswith("_latency-50")]
    data = data.replace([np.inf, -np.inf], np.nan).ffill().fillna(0)
    return data.rename(columns=lambda c: c.replace("_latency-90", "_latency"))


def _window(data: pd.DataFrame, t0: int) -> pd.DataFrame:
    before = data[data["time"] < t0].tail(WINDOW_ROWS)
    after = data[data["time"] >= t0].head(WINDOW_ROWS)
    return pd.concat([before, after], ignore_index=True)


VARIANTS = {
    "A0_original_harness_exact": lambda d, t0: _drop_constant(d),
    "A_original_plus_dataset_arg": lambda d, t0: _drop_constant(d),
    "B_plus_nan_fill": lambda d, t0: _drop_constant(
        d.replace([np.inf, -np.inf], np.nan).ffill().fillna(0)
    ),
    "C_plus_10min_window": lambda d, t0: _drop_constant(_window(d, t0)),
    "D_official_main_py": lambda d, t0: _window(_official_clean(d), t0),
    # Diagnostic only, not a baseline: removes metrics whose normal-period IQR is
    # zero, which RobustScaler silently rescales by 1.
    "F_diagnostic_drop_zero_iqr": lambda d, t0: _drop_zero_iqr(_window(_official_clean(d), t0), t0),
}


def _drop_zero_iqr(data: pd.DataFrame, t0: int) -> pd.DataFrame:
    normal = data[data["time"] < t0]
    iqr = normal.quantile(0.75) - normal.quantile(0.25)
    return data[["time"] + [c for c in data.columns if c != "time" and iqr[c] > 0]]


def _service(metric: str) -> str:
    return metric.split("_")[0].replace("-db", "")


def _services(ranks: list[str]) -> list[str]:
    seen: list[str] = []
    for metric in ranks:
        if (s := _service(metric)) not in seen:
            seen.append(s)
    return seen


def _stats(rows: list[dict]) -> dict:
    n = len(rows)
    wrong = [r for r in rows if r["top_service"] != r["truth"]]
    return {
        "n": n,
        "AC@1": round(sum(r["top_service"] == r["truth"] for r in rows) / n, 3),
        "AC@3": round(sum(r["truth"] in r["services"][:3] for r in rows) / n, 3),
        "redis_top1": sum(r["top_service"] == "redis" for r in rows),
        "wrong_top1": len(wrong),
        "wrong_top1_by_service": dict(Counter(r["top_service"] for r in wrong).most_common()),
        "top1_metric_counts": dict(Counter(r["top_metric"] for r in rows).most_common(8)),
    }


def main() -> None:
    cases = list_cases(suite="re2ob")
    results: dict[str, dict] = {}
    per_case: dict[str, list[dict]] = {}
    for name, prepare in VARIANTS.items():
        rows = []
        for case in tqdm(cases, desc=name):
            t0 = inject_time(case)
            data = prepare(load_metrics(case), t0)
            # The original harness called baro(data, t0) without a dataset name.
            kwargs = {} if name.startswith("A0") else {"dataset": "re2-ob"}
            ranks = list(baro(data, t0, **kwargs)["ranks"])
            services = _services(ranks)
            rows.append(
                {
                    "case": case.name,
                    "truth": case.service,
                    "top_metric": ranks[0],
                    "top_service": services[0],
                    "services": services[:5],
                }
            )
        per_case[name] = rows
        results[name] = _stats(rows)

    official_rows = []
    for path in sorted((OFFICIAL / "baro" / "results").glob("*.json")):
        service, _fault, _case = path.stem.split("_")
        ranks = json.loads(path.read_text())["0"]
        services = _services(ranks)
        official_rows.append(
            {
                "case": path.stem,
                "truth": service,
                "top_metric": ranks[0],
                "top_service": services[0],
                "services": services[:5],
            }
        )
    if official_rows:
        results["E_official_rcaeval_main_py_run"] = _stats(official_rows)

    out = ARTIFACTS / "n1"
    out.mkdir(parents=True, exist_ok=True)
    save_json(out / "redis_hypothesis.json", {"variants": results, "per_case": per_case})
    for name, stats in results.items():
        print(
            f"{name:34s} AC@1={stats['AC@1']:.3f} redis_top1={stats['redis_top1']:2d} "
            f"wrong={stats['wrong_top1']}"
        )


if __name__ == "__main__":
    main()
