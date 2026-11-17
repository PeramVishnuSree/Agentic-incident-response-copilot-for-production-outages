# RCAEval RE1TT — Deep Data Card

## Dataset
- Root: `/Users/charan/Desktop/Masters RCA/datasets/RCAEval`
- Cases: **125**
- Faults: `{'cpu': 25, 'delay': 25, 'disk': 25, 'loss': 25, 'mem': 25}`
- Services: `{'ts-auth-service': 25, 'ts-order-service': 25, 'ts-route-service': 25, 'ts-train-service': 25, 'ts-travel-service': 25}`

## Telemetry profile
- Avg metric columns / case: **213.6**
- Avg sampling interval: **1.00s**
- Avg missing rate: **0.0071**
- Avg constant metric columns: **12.0**
- Avg log lines: **0**
- Avg traces: **0**
- Mean |z| shift on true-service metrics (pre→post): **1709.04**

## Cleaning decisions
- Drop constant / near-constant metric columns before ranking.
- Align all analysis to inject_time; use pre-window as baseline.
- Never put case folder names in model prompts (label leakage).
- Map metrics to services via known Online Boutique prefixes.
- Treat redis_* metrics as redis-cart in our dependency graph.

## Per-fault summary
See `re1tt_deep_eda_summary.json` → `by_fault`.

## Leakage
Case directory names encode root-cause service + fault. Use only as labels.
