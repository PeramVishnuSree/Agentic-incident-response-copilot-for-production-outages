# RCAEval RE2SS — Deep Data Card

## Dataset
- Root: `/Users/charan/Desktop/Masters RCA/datasets/RCAEval`
- Cases: **90**
- Faults: `{'cpu': 15, 'delay': 15, 'disk': 15, 'loss': 15, 'mem': 15, 'socket': 15}`
- Services: `{'carts': 18, 'catalogue': 18, 'orders': 18, 'payment': 18, 'user': 18}`

## Telemetry profile
- Avg metric columns / case: **76.6**
- Avg sampling interval: **1.00s**
- Avg missing rate: **0.0086**
- Avg constant metric columns: **12.7**
- Avg log lines: **84069**
- Avg traces: **0**
- Mean |z| shift on true-service metrics (pre→post): **19730.61**

## Cleaning decisions
- Drop constant / near-constant metric columns before ranking.
- Align all analysis to inject_time; use pre-window as baseline.
- Never put case folder names in model prompts (label leakage).
- Map metrics to services via known Online Boutique prefixes.
- Treat redis_* metrics as redis-cart in our dependency graph.

## Per-fault summary
See `re2ss_deep_eda_summary.json` → `by_fault`.

## Leakage
Case directory names encode root-cause service + fault. Use only as labels.
