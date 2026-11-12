# RCAEval RE2TT — Deep Data Card

## Dataset
- Root: `/Users/charan/Desktop/Masters RCA/datasets/RCAEval`
- Cases: **90**
- Faults: `{'cpu': 15, 'delay': 15, 'disk': 15, 'loss': 15, 'mem': 15, 'socket': 15}`
- Services: `{'ts-auth-service': 18, 'ts-order-service': 18, 'ts-route-service': 18, 'ts-train-service': 18, 'ts-travel-service': 18}`

## Telemetry profile
- Avg metric columns / case: **362.1**
- Avg sampling interval: **1.00s**
- Avg missing rate: **0.0051**
- Avg constant metric columns: **41.8**
- Avg log lines: **233467**
- Avg traces: **748278**
- Mean |z| shift on true-service metrics (pre→post): **1964.49**

## Cleaning decisions
- Drop constant / near-constant metric columns before ranking.
- Align all analysis to inject_time; use pre-window as baseline.
- Never put case folder names in model prompts (label leakage).
- Map metrics to services via known Online Boutique prefixes.
- Treat redis_* metrics as redis-cart in our dependency graph.

## Per-fault summary
See `re2tt_deep_eda_summary.json` → `by_fault`.

## Leakage
Case directory names encode root-cause service + fault. Use only as labels.
