# RCAEval RE3SS — Deep Data Card

## Dataset
- Root: `/Users/charan/Desktop/Masters RCA/datasets/RCAEval`
- Cases: **30**
- Faults: `{'f1': 10, 'f3': 10, 'f4': 7, 'f2': 3}`
- Services: `{'carts': 12, 'front-end': 9, 'orders': 9}`

## Telemetry profile
- Avg metric columns / case: **83.0**
- Avg sampling interval: **1.00s**
- Avg missing rate: **0.0090**
- Avg constant metric columns: **15.9**
- Avg log lines: **76608**
- Avg traces: **0**
- Mean |z| shift on true-service metrics (pre→post): **76.47**

## Cleaning decisions
- Drop constant / near-constant metric columns before ranking.
- Align all analysis to inject_time; use pre-window as baseline.
- Never put case folder names in model prompts (label leakage).
- Map metrics to services via known Online Boutique prefixes.
- Treat redis_* metrics as redis-cart in our dependency graph.

## Per-fault summary
See `re3ss_deep_eda_summary.json` → `by_fault`.

## Leakage
Case directory names encode root-cause service + fault. Use only as labels.
