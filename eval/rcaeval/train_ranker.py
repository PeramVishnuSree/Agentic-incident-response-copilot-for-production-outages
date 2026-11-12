"""Train a simple learned service ranker on RCAEval RE2-OB features."""

from __future__ import annotations

import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import GroupKFold
from tqdm import tqdm

from eval.rcaeval.common import (
    ARTIFACTS,
    REPO_ROOT,
    ac_at_k,
    find_data_root,
    inject_time,
    list_cases,
    load_logs,
    load_metrics,
    metric_to_service,
    save_json,
    services_from_metrics,
)


def _upstreamness_map(services: list[str]) -> dict[str, float]:
    try:
        from correlation_engine.graph import load_dependency_graph, upstreamness

        g = load_dependency_graph(REPO_ROOT / "config" / "dependency-graph.yaml")
        return {svc: float(upstreamness(svc, g)) if svc in g else 0.0 for svc in services}
    except Exception:  # noqa: BLE001
        return {svc: 0.0 for svc in services}


def build_feature_rows(suite: str = "re2ob", window: int = 300) -> pd.DataFrame:
    root = find_data_root()
    cases = list_cases(root, suite=suite)
    rows = []

    for case in tqdm(cases, desc=f"features {suite}"):
        metrics = load_metrics(case)
        logs = load_logs(case)
        t0 = inject_time(case)
        pre = metrics[metrics["time"] < t0]
        post = metrics[(metrics["time"] >= t0) & (metrics["time"] < t0 + window)]
        if pre.empty or post.empty:
            continue

        services = sorted(set(services_from_metrics(metrics)) | {case.service})
        up = _upstreamness_map(services)

        # per-service anomaly / onset / log errors
        for svc in services:
            cols = [c for c in metrics.columns if metric_to_service(c) == svc]
            if not cols:
                continue
            z_vals = []
            onset = None
            for c in cols:
                mu = float(pre[c].mean())
                sigma = float(pre[c].std()) + 1e-9
                if pd.isna(mu) or pd.isna(sigma):
                    continue
                series = ((post[c] - mu) / sigma).abs()
                z_max = float(series.max())
                if pd.isna(z_max):
                    continue
                z_vals.append(z_max)
                # first time z > 3
                hit = series[series > 3]
                if len(hit):
                    t_hit = float(post.loc[hit.index[0], "time"])
                    onset = t_hit - t0 if onset is None else min(onset, t_hit - t0)

            log_err = 0.0
            if not logs.empty and "container_name" in logs.columns:
                sub = logs[logs["container_name"].astype(str).str.contains(svc, regex=False)]
                if len(sub):
                    msgs = sub["message"].astype(str).str.lower()
                    log_err = float(
                        msgs.str.contains("error|fail|exception|timeout", regex=True).mean()
                    )

            rows.append(
                {
                    "case": case.name,
                    "fault": case.fault,
                    "service": svc,
                    "label": 1 if svc == case.service else 0,
                    "anomaly_score": max(z_vals) if z_vals else 0.0,
                    "onset_sec": float(onset) if onset is not None else window,
                    "upstreamness": up.get(svc, 0.0),
                    "log_error_rate": log_err,
                    "n_metrics": len(cols),
                }
            )
    return pd.DataFrame(rows)


def evaluate_ranker(df: pd.DataFrame) -> dict:
    feature_cols = ["anomaly_score", "onset_sec", "upstreamness", "log_error_rate", "n_metrics"]
    # Sparse/missing post-injection windows produce NaNs; GBT needs finite inputs.
    X = df[feature_cols].fillna(0.0).to_numpy()
    y = df["label"].to_numpy()
    groups = df["case"].to_numpy()

    n_splits = min(5, int(pd.Series(groups).nunique()))
    if n_splits < 2:
        raise ValueError(f"Need at least 2 cases to evaluate ranker, got {n_splits}")

    gkf = GroupKFold(n_splits=n_splits)
    case_preds: dict[str, list[tuple[str, float]]] = {}

    for train_idx, test_idx in gkf.split(X, y, groups):
        clf = GradientBoostingClassifier(random_state=42)
        clf.fit(X[train_idx], y[train_idx])
        proba = clf.predict_proba(X[test_idx])
        # probability of class 1
        if proba.shape[1] == 1:
            p1 = proba[:, 0] * 0  # degenerate
        else:
            p1 = proba[:, 1]
        test = df.iloc[test_idx]
        for i, (_, row) in enumerate(test.iterrows()):
            case_preds.setdefault(row["case"], []).append((row["service"], float(p1[i])))

    ac1 = ac3 = 0.0
    truth_map = (
        df[df["label"] == 1][["case", "service"]].drop_duplicates().set_index("case")["service"]
    )
    n = 0
    for case, pairs in case_preds.items():
        ranked = [s for s, _ in sorted(pairs, key=lambda x: -x[1])]
        truth = truth_map.get(case)
        if truth is None:
            continue
        ac1 += ac_at_k(ranked, truth, 1)
        ac3 += ac_at_k(ranked, truth, 3)
        n += 1

    # feature importance from a final full fit
    clf = GradientBoostingClassifier(random_state=42)
    clf.fit(X, y)
    importance = dict(zip(feature_cols, map(float, clf.feature_importances_), strict=True))

    return {
        "n_cases_scored": n,
        "AC@1": ac1 / max(n, 1),
        "AC@3": ac3 / max(n, 1),
        "feature_importance": importance,
        "features": feature_cols,
        "model": "GradientBoostingClassifier",
        "cv": f"GroupKFold({n_splits}) by case",
    }


def run_ranker(suite: str = "re2ob", window: int = 300) -> dict:
    df = build_feature_rows(suite=suite, window=window)
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    df.to_csv(ARTIFACTS / f"{suite}_ranker_features.csv", index=False)
    summary = evaluate_ranker(df)
    summary["suite"] = suite
    summary["window_sec"] = window
    summary["n_rows"] = int(len(df))
    save_json(ARTIFACTS / f"{suite}_ranker_summary.json", summary)
    return summary


if __name__ == "__main__":
    import json

    print(json.dumps(run_ranker("re2ob"), indent=2))
