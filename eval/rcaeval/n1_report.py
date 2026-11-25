"""N1: one table of RE2-OB baselines with 95% bootstrap CIs, per fault.

Inputs (all produced by scripts in this repo, see docs/baselines.md):
* eval/artifacts/rcaeval/official_runs/<method>/results/*.json  (RCAEval main.py)
* eval/artifacts/rcaeval/official_runs/pdiagnose/results/*.json (port of upstream demo)
* eval/artifacts/rcaeval/n1/redis_hypothesis.json               (BARO variants)
* experiments/n3/trajectories/extended30_*/summary.json         (LLM agent, 30 cases)

    uv run python -m eval.rcaeval.n1_report
"""

from __future__ import annotations

import json
import re

from eval.rcaeval.common import ARTIFACTS, REPO_ROOT, save_json
from eval.rcaeval.scoring import METRICS, case_hits, paired_bootstrap, score

OFFICIAL = ARTIFACTS / "official_runs"
OUT = ARTIFACTS / "n1"
FAULTS = ("cpu", "mem", "disk", "socket", "delay", "loss")
ROWS = [
    ("nsigma", "N-Sigma", "RCAEval main.py"),
    ("circa", "CIRCA", "RCAEval main.py"),
    ("mmbaro", "Multi-source BARO", "RCAEval main.py"),
    ("baro", "BARO", "RCAEval main.py"),
    ("rcd", "RCD", "RCAEval main.py (Py 3.8 env)"),
    ("pdiagnose", "PDiagnose", "port of upstream demo"),
    ("e_diagnosis", "E-Diagnosis", "RCAEval main.py"),
    ("dummy", "Random ranking", "RCAEval main.py"),
]


def _service(name: str) -> str:
    name = name.split("_")[0].replace("-db", "")
    return "redis" if name == "redis-cart" else name


def _services(ranks: list[str]) -> list[str]:
    out: list[str] = []
    for item in ranks:
        if (s := _service(item)) not in out:
            out.append(s)
    return out


def load_official(method: str) -> dict[str, list[str]]:
    folder = OFFICIAL / method / "results"
    preds = {}
    for path in sorted(folder.glob("*.json")):
        if path.stem.endswith("_failed"):
            continue
        preds[path.stem] = _services(json.loads(path.read_text())["0"])
    return preds


def truth_of(cases: list[str]) -> dict[str, str]:
    return {case: case.split("_")[0] for case in cases}


def printed_avg5(method: str) -> dict[str, float]:
    stdout = OFFICIAL / method / "stdout.txt"
    if not stdout.exists():
        return {}
    found = re.findall(r"Avg@5-([A-Z]+):\s+([0-9.]+)", stdout.read_text())
    return {fault.lower(): float(value) for fault, value in found}


def _fmt(row, metric: str) -> str:
    return f"{row[metric]:.2f} [{row[metric + '_lo']:.2f}, {row[metric + '_hi']:.2f}]"


def main() -> None:
    all_cases = sorted(load_official("baro"))
    truth = truth_of(all_cases)
    results: dict[str, dict] = {}
    parity: dict[str, float | None] = {}
    per_case_avg5: dict[str, dict[str, float]] = {}

    for key, label, source in ROWS:
        preds = load_official(key)
        if not preds:
            continue
        table = score(preds, truth)
        results[key] = {
            "label": label,
            "source": source,
            "n_predicted": len(preds),
            "table": json.loads(table.to_json(orient="index")),
        }
        per_case_avg5[key] = {c: case_hits(preds.get(c, []), truth[c])["Avg@5"] for c in all_cases}
        printed = printed_avg5(key)
        if printed:
            diffs = [abs(round(table.loc[f, "Avg@5"], 2) - printed[f]) for f in printed]
            parity[key] = round(max(diffs), 3)

    hypothesis = json.loads((OUT / "redis_hypothesis.json").read_text())
    variants = {
        "A0_original_harness_exact": ("BARO, our original harness (the 0.30)", "diagnostic"),
        "F_diagnostic_drop_zero_iqr": ("BARO + zero-IQR guard", "diagnostic, not a baseline"),
    }
    for name, (label, source) in variants.items():
        rows = hypothesis["per_case"].get(name, [])
        preds = {r["case"].removeprefix("re2ob_"): r["services"] for r in rows}
        preds = {k: [_service(s) for s in v] for k, v in preds.items()}
        if preds:
            table = score(preds, truth)
            results[name] = {
                "label": label,
                "source": source,
                "n_predicted": len(preds),
                "table": json.loads(table.to_json(orient="index")),
            }

    agent_summary = sorted(
        (REPO_ROOT / "experiments" / "n3" / "trajectories").glob("extended30_*/summary.json")
    )
    agent = None
    if agent_summary:
        summary = json.loads(agent_summary[-1].read_text())
        subset = [c["case"].removeprefix("re2ob_") for c in summary["cases"]]
        agent_preds = {
            c["case"].removeprefix("re2ob_"): [_service(s) for s in c["top_services"]]
            for c in summary["cases"]
        }
        sub_truth = {c: truth[c] for c in subset}
        compare = {"agent": score(agent_preds, sub_truth)}
        tests = {}
        for key in ("nsigma", "circa", "pdiagnose", "rcd", "baro", "mmbaro"):
            preds = load_official(key)
            if not set(subset) <= set(preds):
                continue
            compare[key] = score(preds, sub_truth)
            for metric in ("AC@1", "Avg@5"):
                a = [case_hits(agent_preds.get(c, []), sub_truth[c])[metric] for c in subset]
                b = [case_hits(preds.get(c, []), sub_truth[c])[metric] for c in subset]
                diff, (lo, hi) = paired_bootstrap(a, b)
                tests[f"agent_minus_{key}_{metric}"] = {"diff": diff, "ci": [lo, hi]}
        agent = {
            "model": summary["model"],
            "prompt": summary.get("prompt"),
            "n_cases": len(subset),
            "valid_tool_call_rate": summary.get("valid_tool_call_rate"),
            "mean_seconds_per_case": summary.get("mean_seconds_per_case"),
            "tables": {k: json.loads(v.to_json(orient="index")) for k, v in compare.items()},
            "paired_bootstrap": tests,
        }

    report = {
        "n_cases": len(all_cases),
        "methods": results,
        "avg5_parity_vs_main_py": parity,
        "agent_subset": agent,
    }
    save_json(OUT / "n1_results.json", report)
    (OUT / "n1_table.md").write_text(render(report))
    print(render(report))


def render(report: dict) -> str:
    lines = [
        f"RE2-OB, {report['n_cases']} cases, service level. Mean [95% bootstrap CI].",
        "",
        "| Method | Source | AC@1 | AC@3 | AC@5 | Avg@5 |",
        "|---|---|---|---|---|---|",
    ]
    for entry in report["methods"].values():
        row = entry["table"]["all"]
        n = entry["n_predicted"]
        note = "" if n == report["n_cases"] else f" ({n}/{report['n_cases']} cases)"
        lines.append(
            f"| {entry['label']}{note} | {entry['source']} | "
            + " | ".join(_fmt(row, m) for m in METRICS)
            + " |"
        )
    lines += [
        "",
        "Avg@5 per fault type:",
        "",
        "| Method | " + " | ".join(f.upper() for f in FAULTS) + " |",
        "|---|" + "---|" * len(FAULTS),
    ]
    for entry in report["methods"].values():
        table = entry["table"]
        cells = [f"{table[f]['Avg@5']:.2f}" if f in table else "-" for f in FAULTS]
        lines.append(f"| {entry['label']} | " + " | ".join(cells) + " |")
    agent = report.get("agent_subset")
    if agent:
        lines += [
            "",
            f"Same {agent['n_cases']} cases (one per service x fault), "
            f"LLM agent = {agent['model']} prompt {agent['prompt']}:",
            "",
            "| Method | AC@1 | AC@3 | Avg@5 |",
            "|---|---|---|---|",
        ]
        for key, table in agent["tables"].items():
            row = table["all"]
            name = "LLM agent (N3)" if key == "agent" else report["methods"][key]["label"]
            lines.append(
                f"| {name} | {_fmt(row, 'AC@1')} | {_fmt(row, 'AC@3')} | {_fmt(row, 'Avg@5')} |"
            )
        lines += ["", "Paired bootstrap, agent minus baseline (95% CI):", ""]
        for name, test in agent["paired_bootstrap"].items():
            lines.append(
                f"- {name}: {test['diff']:+.2f} [{test['ci'][0]:+.2f}, {test['ci'][1]:+.2f}]"
            )
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
