# RCAEval RE3TT — Deep Data Card

## Dataset
- Root: `/Users/charan/Desktop/Masters RCA/datasets/RCAEval`
- Cases: **30**
- Faults: `{'f1': 7, 'f2': 7, 'f3': 10, 'f4': 6}`
- Services: `{'ts-auth-service': 15, 'ts-route-service': 15}`

## Telemetry profile
- Avg metric columns / case: **315.2**
- Avg sampling interval: **1.00s**
- Avg missing rate: **0.0633**
- Avg constant metric columns: **27.4**
- Avg log lines: **54262**
- Avg traces: **138423**
- Mean |z| shift on true-service metrics (pre→post): **8.37**

## Cleaning decisions
- Drop constant / near-constant metric columns before ranking.
- Align all analysis to inject_time; use pre-window as baseline.
- Never put case folder names in model prompts (label leakage).
- Map metrics to services via known Online Boutique prefixes.
- Treat redis_* metrics as redis-cart in our dependency graph.

## Per-fault summary
See `re3tt_deep_eda_summary.json` → `by_fault`.

## Leakage
Case directory names encode root-cause service + fault. Use only as labels.
