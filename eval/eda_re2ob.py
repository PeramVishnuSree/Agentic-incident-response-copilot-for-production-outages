"""X0 — Exploratory Data Analysis on RCAEval RE2 Online Boutique cases.

Looks for a local Hugging Face / Zenodo extract under:
  ../datasets/RCAEval   (Masters RCA folder)
  ./datasets/RCAEval
  $RCAEVAL_DIR

Writes:
  eval/artifacts/re2ob_data_card.md
  eval/artifacts/re2ob_eda_summary.json
"""

from __future__ import annotations

import json
import os
import statistics
from collections import Counter, defaultdict
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _candidate_roots() -> list[Path]:
    env = os.environ.get("RCAEVAL_DIR")
    roots = []
    if env:
        roots.append(Path(env))
    roots.extend(
        [
            REPO_ROOT.parent / "datasets" / "RCAEval",
            REPO_ROOT / "datasets" / "RCAEval",
            Path.home() / "Desktop" / "Masters RCA" / "datasets" / "RCAEval",
        ]
    )
    return roots


def find_re2ob_cases() -> list[Path]:
    for root in _candidate_roots():
        if not root.is_dir():
            continue
        cases = sorted(p for p in root.iterdir() if p.is_dir() and p.name.startswith("re2ob_"))
        if cases:
            return cases
        # Zenodo-style nested layout: RE2-OB/<service>_<fault>/<rep>/
        nested = list(root.glob("**/inject_time.txt"))
        if nested:
            return sorted({p.parent for p in nested if "OB" in str(p) or "ob" in str(p)})
    return []


def _parse_case_name(name: str) -> tuple[str, str, str]:
    # re2ob_cartservice_cpu_1 -> cartservice, cpu, 1
    parts = name.split("_")
    if len(parts) < 4:
        return "unknown", "unknown", "0"
    return parts[1], parts[2], parts[-1]


def analyze(cases: list[Path]) -> dict:
    fault_counts: Counter[str] = Counter()
    service_counts: Counter[str] = Counter()
    file_kinds: Counter[str] = Counter()
    sizes: list[int] = []
    missing: list[str] = []
    leakage_flags: list[str] = []

    per_fault_files: dict[str, list[str]] = defaultdict(list)

    for case in cases:
        svc, fault, _rep = _parse_case_name(case.name)
        fault_counts[fault] += 1
        service_counts[svc] += 1
        names = [p.name for p in case.iterdir() if p.is_file()]
        for n in names:
            file_kinds[n.split(".")[-1] if "." in n else n] += 1
            per_fault_files[fault].append(n)
            sizes.append((case / n).stat().st_size)
        expected_any = {"metrics.json", "metrics.parquet", "data.csv", "inject_time.txt"}
        if not (set(names) & expected_any) and "inject_time.txt" not in names:
            # HF parquet layout often uses single parquet per modality
            if not any(n.endswith(".parquet") for n in names):
                missing.append(case.name)
        # Leakage check: folder name encodes ground-truth service+fault.
        # That is OK for evaluation labels, but models must NOT see the path.
        leakage_flags.append(f"{case.name} encodes label service={svc} fault={fault}")

    return {
        "n_cases": len(cases),
        "fault_counts": dict(fault_counts),
        "service_counts": dict(service_counts),
        "file_extension_counts": dict(file_kinds),
        "total_bytes": sum(sizes),
        "median_file_bytes": statistics.median(sizes) if sizes else 0,
        "cases_missing_expected_files": missing[:20],
        "leakage_notes": [
            "Case directory names encode root-cause service and fault type.",
            "Keep paths out of model prompts; use inject_time + telemetry only.",
            f"example: {leakage_flags[0]}" if leakage_flags else "none",
        ],
        "data_root": str(cases[0].parent) if cases else None,
    }


def write_artifacts(summary: dict) -> tuple[Path, Path]:
    out_dir = REPO_ROOT / "eval" / "artifacts"
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "re2ob_eda_summary.json"
    card_path = out_dir / "re2ob_data_card.md"
    json_path.write_text(json.dumps(summary, indent=2))

    card = f"""# RCAEval RE2-OB Data Card (X0)

## Dataset
- **Name:** RCAEval RE2 Online Boutique
- **Source:** public benchmark (Zenodo / Hugging Face) — not created by this team
- **Local root:** `{summary.get("data_root")}`
- **Cases found:** {summary.get("n_cases")}

## Contents
- Fault type counts: `{summary.get("fault_counts")}`
- Service counts: `{summary.get("service_counts")}`
- File extensions seen: `{summary.get("file_extension_counts")}`
- Approx total bytes scanned: {summary.get("total_bytes")}

## Quality / leakage
{chr(10).join('- ' + n for n in summary.get("leakage_notes", []))}

## Cleaning decisions
1. Use case folders only as **labels** (service, fault, repetition).
2. Feed models **metrics/logs/traces** + inject time — never the folder name.
3. Align timestamps relative to `inject_time` when present.
4. Drop constant / all-null metric columns during ranking feature build (Sprint 3+).

## Next experiments
- X1 baselines (BARO / RCD / CIRCA) on RE2-OB
- X2 correlation window sweep
- X3 LLM bake-off on a 30-case subset
"""
    card_path.write_text(card)
    return json_path, card_path


def main() -> int:
    cases = find_re2ob_cases()
    if not cases:
        print(
            "No RE2-OB cases found yet. Download with:\n"
            "  snapshot_download(repo_id='phamquiluan/RCAEval', allow_patterns='re2ob*', ...)\n"
            "or set RCAEVAL_DIR."
        )
        return 1
    summary = analyze(cases)
    json_path, card_path = write_artifacts(summary)
    print(json.dumps(summary, indent=2))
    print(f"\nWrote {json_path}")
    print(f"Wrote {card_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
