# RCAEval RE2-OB Data Card (X0)

## Dataset
- **Name:** RCAEval RE2 Online Boutique
- **Source:** public benchmark (Zenodo / Hugging Face) — not created by this team
- **Local root:** `/Users/charan/Desktop/Masters RCA/datasets/RCAEval`
- **Cases found:** 90

## Contents
- Fault type counts: `{'cpu': 15, 'delay': 15, 'disk': 15, 'loss': 15, 'mem': 15, 'socket': 15}`
- Service counts: `{'checkoutservice': 18, 'currencyservice': 18, 'emailservice': 18, 'productcatalogservice': 18, 'recommendationservice': 18}`
- File extensions seen: `{'parquet': 270, 'txt': 90}`
- Approx total bytes scanned: 922484805

## Quality / leakage
- Case directory names encode root-cause service and fault type.
- Keep paths out of model prompts; use inject_time + telemetry only.
- example: re2ob_checkoutservice_cpu_1 encodes label service=checkoutservice fault=cpu

## Cleaning decisions
1. Use case folders only as **labels** (service, fault, repetition).
2. Feed models **metrics/logs/traces** + inject time — never the folder name.
3. Align timestamps relative to `inject_time` when present.
4. Drop constant / all-null metric columns during ranking feature build (Sprint 3+).

## Next experiments
- X1 baselines (BARO / RCD / CIRCA) on RE2-OB
- X2 correlation window sweep
- X3 LLM bake-off on a 30-case subset
