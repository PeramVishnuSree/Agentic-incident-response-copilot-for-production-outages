"""Sweep correlation/analysis windows on RCAEval RE2-OB.

For each case we score services by post-inject anomaly magnitude inside windows
of different lengths, then measure AC@1 / AC@3. This estimates how large W
should be for our correlation stage.
"""

from __future__ import annotations

from collections import defaultdict

from tqdm import tqdm

from eval.rcaeval.common import (
    ARTIFACTS,
    ac_at_k,
    find_data_root,
    inject_time,
    list_cases,
    load_metrics,
    metric_to_service,
    save_json,
)

WINDOWS_SEC = [30, 60, 120, 300, 600, 900]


def _service_anomaly_scores(metrics: pd.DataFrame, t0: int, window: int) -> dict[str, float]:
    pre = metrics[metrics["time"] < t0]
    post = metrics[(metrics["time"] >= t0) & (metrics["time"] < t0 + window)]
    if pre.empty or post.empty:
        return {}

    scores: dict[str, float] = defaultdict(float)
    for col in metrics.columns:
        if col == "time":
            continue
        svc = metric_to_service(col)
        if not svc:
            continue
        mu = float(pre[col].mean())
        sigma = float(pre[col].std()) + 1e-9
        z = abs(float(post[col].mean()) - mu) / sigma
        scores[svc] = max(scores[svc], z)
    return dict(scores)


def rank_services(scores: dict[str, float]) -> list[str]:
    return [s for s, _ in sorted(scores.items(), key=lambda kv: (-kv[1], kv[0]))]


def run_window_sweep(suite: str = "re2ob", limit: int | None = None) -> dict:
    root = find_data_root()
    cases = list_cases(root, suite=suite)
    if limit:
        cases = cases[:limit]

    results_by_w: dict[int, list[dict]] = {w: [] for w in WINDOWS_SEC}

    for case in tqdm(cases, desc=f"window-sweep {suite}"):
        metrics = load_metrics(case)
        t0 = inject_time(case)
        for w in WINDOWS_SEC:
            scores = _service_anomaly_scores(metrics, t0, w)
            ranked = rank_services(scores)
            results_by_w[w].append(
                {
                    "case": case.name,
                    "truth": case.service,
                    "fault": case.fault,
                    "top": ranked[:5],
                    "ac1": ac_at_k(ranked, case.service, 1),
                    "ac3": ac_at_k(ranked, case.service, 3),
                }
            )

    summary = {"suite": suite, "windows_sec": WINDOWS_SEC, "results": {}}
    best_w, best_ac3 = None, -1.0
    for w, rows in results_by_w.items():
        ac1 = sum(r["ac1"] for r in rows) / max(len(rows), 1)
        ac3 = sum(r["ac3"] for r in rows) / max(len(rows), 1)
        summary["results"][str(w)] = {
            "AC@1": ac1,
            "AC@3": ac3,
            "n": len(rows),
        }
        if ac3 > best_ac3:
            best_ac3, best_w = ac3, w

    summary["chosen_window_sec"] = best_w
    summary["reason"] = (
        f"Chose W={best_w}s because it maximises AC@3 ({best_ac3:.3f}) "
        "on labelled RE2-OB anomaly-window ranking."
    )

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    save_json(ARTIFACTS / f"{suite}_window_sweep.json", summary)
    save_json(ARTIFACTS / f"{suite}_window_sweep_cases.json", results_by_w)
    return summary


if __name__ == "__main__":
    import json
    import sys

    lim = int(sys.argv[1]) if len(sys.argv) > 1 else None
    print(json.dumps(run_window_sweep("re2ob", limit=lim), indent=2))
