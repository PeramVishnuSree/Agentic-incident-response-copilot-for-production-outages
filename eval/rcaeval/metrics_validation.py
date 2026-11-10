"""Validate evaluation metrics against RCAEval baselines (professor item #3).

Produces:
- multi-baseline scores on RE2-OB (BARO, N-Sigma, E-Diagnosis)
- bootstrap 95% CIs (overall + per fault)
- revised Acc@1 / Acc@3 targets relative to BARO
- human-study sample-size estimate from pilot variance
"""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.model_selection import GroupKFold

from eval.rcaeval.baselines import DEFAULT_METHODS, run_baselines
from eval.rcaeval.common import ARTIFACTS, ac_at_k, save_json
from eval.rcaeval.train_ranker import build_feature_rows

RNG = np.random.default_rng(42)
Z_95 = 1.96
Z_80 = 0.8416  # one-sided power ~80%
Z_90 = 1.2816


def bootstrap_mean_ci(
    values: list[float] | np.ndarray,
    n_boot: int = 5000,
    alpha: float = 0.05,
    rng: np.random.Generator | None = None,
) -> dict:
    arr = np.asarray(values, dtype=float)
    if arr.size == 0:
        return {"n": 0, "mean": None, "ci_low": None, "ci_high": None}
    rng = rng or RNG
    means = np.empty(n_boot, dtype=float)
    n = arr.size
    for i in range(n_boot):
        sample = arr[rng.integers(0, n, size=n)]
        means[i] = float(sample.mean())
    low = float(np.quantile(means, alpha / 2))
    high = float(np.quantile(means, 1 - alpha / 2))
    return {
        "n": int(n),
        "mean": float(arr.mean()),
        "ci_low": low,
        "ci_high": high,
        "std": float(arr.std(ddof=1)) if n > 1 else 0.0,
    }


def summarize_case_rows(rows: list[dict], n_boot: int = 5000) -> dict:
    overall = {
        "AC@1": bootstrap_mean_ci([r["ac1"] for r in rows], n_boot=n_boot),
        "AC@3": bootstrap_mean_ci([r["ac3"] for r in rows], n_boot=n_boot),
        "AC@5": bootstrap_mean_ci([r["ac5"] for r in rows], n_boot=n_boot),
        "Avg@5": bootstrap_mean_ci([r["avg5"] for r in rows], n_boot=n_boot),
    }
    by_fault: dict[str, dict] = {}
    faults = sorted({r["fault"] for r in rows})
    for fault in faults:
        subset = [r for r in rows if r["fault"] == fault]
        by_fault[fault] = {
            "AC@1": bootstrap_mean_ci([r["ac1"] for r in subset], n_boot=n_boot),
            "AC@3": bootstrap_mean_ci([r["ac3"] for r in subset], n_boot=n_boot),
            "Avg@5": bootstrap_mean_ci([r["avg5"] for r in subset], n_boot=n_boot),
        }
    return {"overall": overall, "by_fault": by_fault}


def ranker_case_scores(suite: str = "re2ob", window: int = 120) -> list[dict]:
    """Leave-case-out style GroupKFold scores for the GBT ranker."""
    df = build_feature_rows(suite=suite, window=window)
    feature_cols = ["anomaly_score", "onset_sec", "upstreamness", "log_error_rate", "n_metrics"]
    X = df[feature_cols].fillna(0.0).to_numpy()
    y = df["label"].to_numpy()
    groups = df["case"].to_numpy()
    n_splits = min(5, int(pd.Series(groups).nunique()))
    gkf = GroupKFold(n_splits=n_splits)

    case_preds: dict[str, list[tuple[str, float]]] = {}
    fault_map = df.drop_duplicates("case").set_index("case")["fault"].to_dict()
    truth_map = (
        df[df["label"] == 1][["case", "service"]].drop_duplicates().set_index("case")["service"]
    )

    for train_idx, test_idx in gkf.split(X, y, groups):
        clf = GradientBoostingClassifier(random_state=42)
        clf.fit(X[train_idx], y[train_idx])
        proba = clf.predict_proba(X[test_idx])
        p1 = proba[:, 1] if proba.shape[1] > 1 else np.zeros(len(test_idx))
        test = df.iloc[test_idx]
        for i, (_, row) in enumerate(test.iterrows()):
            case_preds.setdefault(row["case"], []).append((row["service"], float(p1[i])))

    rows = []
    for case, pairs in case_preds.items():
        ranked = [s for s, _ in sorted(pairs, key=lambda x: -x[1])]
        truth = truth_map.get(case)
        if truth is None:
            continue
        rows.append(
            {
                "case": case,
                "fault": fault_map.get(case, "unknown"),
                "truth": truth,
                "method": "gbt_ranker",
                "top_services": ranked[:10],
                "ac1": ac_at_k(ranked, truth, 1),
                "ac3": ac_at_k(ranked, truth, 3),
                "ac5": ac_at_k(ranked, truth, 5),
                "avg5": sum(ac_at_k(ranked, truth, k) for k in range(1, 6)) / 5.0,
            }
        )
    return rows


def revised_targets(baro_ci: dict, nsigma_ci: dict | None = None) -> dict:
    """Set engineering targets relative to BARO (+ stronger N-Sigma when available)."""
    overall = baro_ci["overall"]
    baro_ac1 = overall["AC@1"]["mean"]
    baro_ac3 = overall["AC@3"]["mean"]
    baro_avg5 = overall["Avg@5"]["mean"]

    # Clear BARO's upper CI (minimum scientifically grounded bar).
    clear_baro_ac1 = overall["AC@1"]["ci_high"] + 0.05
    # Product gate: also remain competitive with the best simple metric baseline.
    nsigma_ac1 = None
    if nsigma_ci is not None:
        nsigma_ac1 = nsigma_ci["overall"]["AC@1"]["mean"]
        competitive = nsigma_ci["overall"]["AC@1"]["ci_low"]
    else:
        competitive = 0.70
    gate_ac1 = max(clear_baro_ac1, baro_ac1 + 0.25, competitive)
    gate_ac3 = max(baro_ac3, 0.90)  # BARO already ~0.92 on RE2-OB
    stretch_ac1 = max(gate_ac1, nsigma_ac1 or 0.85, 0.85)
    stretch_ac3 = max(gate_ac3, 0.95)

    per_fault = {}
    for fault, mets in baro_ci["by_fault"].items():
        b1 = mets["AC@1"]["mean"]
        b3 = mets["AC@3"]["mean"]
        # Per-fault gate: exceed BARO; if BARO already strong (>=0.7), hold the mean.
        if b1 >= 0.70:
            t1 = b1
        else:
            t1 = min(0.90, max(b1 + 0.25, mets["AC@1"]["ci_high"] + 0.10, 0.50))
        t3 = max(b3, 0.85)
        per_fault[fault] = {
            "baro_AC@1": b1,
            "baro_AC@1_ci": [mets["AC@1"]["ci_low"], mets["AC@1"]["ci_high"]],
            "target_AC@1": round(t1, 3),
            "baro_AC@3": b3,
            "target_AC@3": round(t3, 3),
            "baro_Avg@5": mets["Avg@5"]["mean"],
        }

    return {
        "replaced": {
            "old_workbook_AC@1": 0.60,
            "old_workbook_AC@3": 0.85,
            "reason": (
                "Workbook 1 60%/85% were not derived from data. "
                "Targets now sit above RE2-OB BARO bootstrap CIs and remain "
                "competitive with N-Sigma on the same suite."
            ),
        },
        "overall": {
            "reference_BARO_AC@1": round(baro_ac1, 3),
            "reference_BARO_AC@1_95CI": [
                round(overall["AC@1"]["ci_low"], 3),
                round(overall["AC@1"]["ci_high"], 3),
            ],
            "reference_BARO_AC@3": round(baro_ac3, 3),
            "reference_BARO_Avg@5": round(baro_avg5, 3),
            "reference_NSigma_AC@1": None if nsigma_ac1 is None else round(nsigma_ac1, 3),
            "clear_BARO_AC@1": round(clear_baro_ac1, 3),
            "gate_AC@1": round(gate_ac1, 3),
            "gate_AC@3": round(gate_ac3, 3),
            "stretch_AC@1": round(stretch_ac1, 3),
            "stretch_AC@3": round(stretch_ac3, 3),
            "gate_Avg@5": round(
                max(baro_avg5 + 0.05, overall["Avg@5"]["ci_high"], 0.86),
                3,
            ),
        },
        "by_fault": per_fault,
    }


def sample_size_two_proportions(p0: float, p1: float, alpha: float = 0.05, power: float = 0.8) -> int:
    """Two-sided equal-n sample size per arm for independent proportions."""
    if abs(p1 - p0) < 1e-9:
        return 10**9
    z_a = Z_95 if abs(alpha - 0.05) < 1e-9 else 1.96
    z_b = Z_80 if abs(power - 0.8) < 1e-9 else Z_90
    num = (z_a * math.sqrt(2 * p0 * (1 - p0)) + z_b * math.sqrt(p0 * (1 - p0) + p1 * (1 - p1))) ** 2
    den = (p1 - p0) ** 2
    return int(math.ceil(num / den))


def sample_size_estimate_proportion(p: float, margin: float = 0.05, alpha: float = 0.05) -> int:
    z = Z_95 if abs(alpha - 0.05) < 1e-9 else 1.96
    return int(math.ceil((z**2) * p * (1 - p) / (margin**2)))


def human_study_sizing(baro_rows: list[dict], ranker_rows: list[dict]) -> dict:
    """Size the human pilot from RE2-OB pilot variance (accuracy endpoint)."""
    baro_ac1 = float(np.mean([r["ac1"] for r in baro_rows]))
    ranker_ac1 = float(np.mean([r["ac1"] for r in ranker_rows]))
    baro_ac3 = float(np.mean([r["ac3"] for r in baro_rows]))

    # Conservative detection target: show agent beats BARO by +15pp AC@1.
    detect_p1 = min(0.95, baro_ac1 + 0.15)
    n_per_arm_detect = sample_size_two_proportions(baro_ac1, detect_p1, power=0.8)
    # Estimate our system AC@1 within ±5pp (95% CI), using ranker pilot p.
    n_estimate = sample_size_estimate_proportion(max(0.05, min(0.95, ranker_ac1)), margin=0.05)
    # Per-fault stratum: worst-case variance p=0.5, want ±15pp inside each fault type.
    n_per_fault = sample_size_estimate_proportion(0.5, margin=0.15)
    n_faults = len({r["fault"] for r in baro_rows})

    return {
        "endpoint": "top-1 accuracy (binary hit on labelled RCAEval / Chaos cases)",
        "pilot_BARO_AC@1": round(baro_ac1, 3),
        "pilot_BARO_AC@3": round(baro_ac3, 3),
        "pilot_ranker_AC@1": round(ranker_ac1, 3),
        "detect_improvement": {
            "from": round(baro_ac1, 3),
            "to": round(detect_p1, 3),
            "alpha": 0.05,
            "power": 0.80,
            "n_cases_per_arm": n_per_arm_detect,
            "note": "Independent two-proportion; use paired McNemar on shared cases when possible.",
        },
        "estimate_own_AC@1_within_5pp": {
            "p_hat": round(ranker_ac1, 3),
            "margin": 0.05,
            "n_cases": n_estimate,
        },
        "human_study_recommendation": {
            "labelled_fault_cases_total": max(n_per_arm_detect, n_estimate),
            "per_fault_stratum_min": n_per_fault,
            "fault_types": n_faults,
            "human_participants_for_TTRC": {
                "within_subject": 12,
                "rationale": (
                    "Accuracy n comes from RCAEval variance above. For human time-to-RCA, "
                    "a within-subject pilot of ~12 operators × ≥6 scenarios estimates "
                    "TTRC SD; then re-size Semester B with that SD (no human TTRC yet)."
                ),
            },
        },
    }


def _fmt_ci(block: dict) -> str:
    return f"{block['mean']:.3f} [{block['ci_low']:.3f}, {block['ci_high']:.3f}]"


def write_report(payload: dict, path: Path) -> None:
    baro = payload["baselines"]["baro"]["ci"]
    targets = payload["revised_targets"]
    study = payload["human_study_sizing"]
    lines = [
        "# Metrics validation (Workbook professor item #3)",
        "",
        "**Question:** Have any preliminary experiments validated the evaluation metrics?",
        "**Answer now:** Yes — RE2-OB pilot with BARO + other RCAEval metric baselines,",
        "bootstrap 95% CIs, revised targets relative to BARO (per fault), and a study-size calc.",
        "",
        f"Suite: `{payload['suite']}` · cases: **{payload['n_cases']}** · date: {payload['date']}",
        "",
        "## 1. Baselines on RE2-OB (empirical reference)",
        "",
        "| Method | AC@1 (95% CI) | AC@3 (95% CI) | Avg@5 (95% CI) |",
        "|--------|--------------:|--------------:|---------------:|",
    ]
    for method, block in payload["baselines"].items():
        ci = block["ci"]["overall"]
        lines.append(
            f"| {method} | {_fmt_ci(ci['AC@1'])} | {_fmt_ci(ci['AC@3'])} | {_fmt_ci(ci['Avg@5'])} |"
        )

    lines += [
        "",
        "Published context: BARO paper/repo reports Avg@5 ≈ 0.86 on Online Boutique metric data;",
        f"our RE2-OB BARO Avg@5 = **{baro['overall']['Avg@5']['mean']:.3f}** "
        f"(95% CI {_fmt_ci(baro['overall']['Avg@5']).split(' ', 1)[1]}).",
        "",
        "### BARO per fault (95% bootstrap CI)",
        "",
        "| Fault | AC@1 | AC@3 | Avg@5 |",
        "|-------|-----:|-----:|------:|",
    ]
    for fault, mets in baro["by_fault"].items():
        lines.append(
            f"| {fault} | {_fmt_ci(mets['AC@1'])} | {_fmt_ci(mets['AC@3'])} | {_fmt_ci(mets['Avg@5'])} |"
        )

    o = targets["overall"]
    lines += [
        "",
        "## 2. Revised targets (replace workbook 60% / 85%)",
        "",
        f"- Old (unvalidated): AC@1 ≥ {targets['replaced']['old_workbook_AC@1']}, "
        f"AC@3 ≥ {targets['replaced']['old_workbook_AC@3']}",
        f"- Clear BARO 95% CI: AC@1 ≥ **{o['clear_BARO_AC@1']}**",
        f"- **Engineering gate** (beat BARO + competitive with N-Sigma): "
        f"AC@1 ≥ **{o['gate_AC@1']}**, AC@3 ≥ **{o['gate_AC@3']}**, "
        f"Avg@5 ≥ **{o['gate_Avg@5']}**",
        f"- **Stretch:** AC@1 ≥ **{o['stretch_AC@1']}**, AC@3 ≥ **{o['stretch_AC@3']}**",
        f"- BARO reference AC@1 = {o['reference_BARO_AC@1']} "
        f"(95% CI {o['reference_BARO_AC@1_95CI']}); "
        f"N-Sigma AC@1 = {o.get('reference_NSigma_AC@1')}",
        "",
        "| Fault | BARO AC@1 | Target AC@1 | BARO AC@3 | Target AC@3 |",
        "|-------|----------:|------------:|----------:|------------:|",
    ]
    for fault, row in targets["by_fault"].items():
        lines.append(
            f"| {fault} | {row['baro_AC@1']:.3f} | **{row['target_AC@1']:.3f}** | "
            f"{row['baro_AC@3']:.3f} | **{row['target_AC@3']:.3f}** |"
        )

    hs = study["human_study_recommendation"]
    lines += [
        "",
        "## 3. Human-study sizing from pilot variance",
        "",
        f"- Pilot BARO AC@1 = {study['pilot_BARO_AC@1']}, ranker AC@1 = {study['pilot_ranker_AC@1']}",
        f"- To detect +15pp over BARO (80% power, α=0.05): "
        f"**n ≈ {study['detect_improvement']['n_cases_per_arm']} labelled cases / arm**",
        f"- To estimate our AC@1 within ±5pp: **n ≈ {study['estimate_own_AC@1_within_5pp']['n_cases']}**",
        f"- Per-fault stratum (±15pp, worst-case p=0.5): "
        f"**n ≈ {hs['per_fault_stratum_min']} / fault** × {hs['fault_types']} faults",
        f"- Recommended labelled eval budget: **≥ {hs['labelled_fault_cases_total']} cases**",
        f"- Human TTRC pilot: **~{hs['human_participants_for_TTRC']['within_subject']} "
        f"operators** (within-subject) to estimate SD, then re-size Semester B",
        "",
        "## 4. What this closes",
        "",
        "- Metrics AC@k / Avg@5 are empirically grounded on public RCAEval RE2-OB.",
        "- Targets are relative to BARO (overall + per fault), with bootstrap CIs.",
        "- Pilot variance sizes the accuracy arm of the human study; TTRC still needs a timed pilot.",
        "",
        "## Reproduce",
        "",
        "```bash",
        "uv run python -m eval.rcaeval.metrics_validation --suite re2ob",
        "```",
        "",
        "Artifacts: `re2ob_*_cases.json`, `re2ob_metrics_validation.json`, this file.",
        "",
    ]
    path.write_text("\n".join(lines))


def main() -> int:
    from datetime import date

    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", default="re2ob")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--n-boot", type=int, default=5000)
    parser.add_argument("--window", type=int, default=120)
    parser.add_argument(
        "--skip-baselines",
        action="store_true",
        help="Reuse existing case JSON if present",
    )
    args = parser.parse_args()

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    suite = args.suite

    if not args.skip_baselines:
        run_baselines(suite=suite, limit=args.limit, methods=DEFAULT_METHODS)

    baseline_ci: dict = {}
    baseline_rows: dict[str, list] = {}
    for method in DEFAULT_METHODS:
        path = ARTIFACTS / f"{suite}_{method}_cases.json"
        # baro also written as suite_baro_cases.json
        if not path.exists() and method == "baro":
            path = ARTIFACTS / f"{suite}_baro_cases.json"
        rows = __import__("json").loads(path.read_text())
        # Drop hard failures from CI mean? keep scored zeros (fair).
        baseline_rows[method] = rows
        baseline_ci[method] = {
            "summary_path": str(path),
            "ci": summarize_case_rows(rows, n_boot=args.n_boot),
        }

    print("== GBT ranker case scores ==")
    ranker_rows = ranker_case_scores(suite=suite, window=args.window)
    if args.limit:
        ranker_rows = ranker_rows[: args.limit]
    save_json(ARTIFACTS / f"{suite}_gbt_ranker_cases.json", ranker_rows)
    ranker_ci = summarize_case_rows(ranker_rows, n_boot=args.n_boot)
    baseline_ci["gbt_ranker"] = {"ci": ranker_ci}

    targets = revised_targets(
        baseline_ci["baro"]["ci"],
        nsigma_ci=baseline_ci.get("nsigma", {}).get("ci"),
    )
    study = human_study_sizing(baseline_rows["baro"], ranker_rows)

    payload = {
        "date": str(date.today()),
        "suite": suite,
        "n_cases": len(baseline_rows["baro"]),
        "n_boot": args.n_boot,
        "baselines": baseline_ci,
        "revised_targets": targets,
        "human_study_sizing": study,
        "status": {
            "professor_item_3": "fixed",
            "baselines_run": list(DEFAULT_METHODS) + ["gbt_ranker"],
            "bootstrap_cis": True,
            "targets_rewritten_vs_baro": True,
            "human_study_sized_from_pilot": True,
        },
    }
    save_json(ARTIFACTS / f"{suite}_metrics_validation.json", payload)
    report = ARTIFACTS / "METRICS_VALIDATION.md"
    write_report(payload, report)
    # Also suite-prefixed copy
    write_report(payload, ARTIFACTS / f"{suite}_METRICS_VALIDATION.md")
    print(report.read_text())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
