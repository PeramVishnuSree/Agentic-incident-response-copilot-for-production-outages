# RCAEval RE3OB — Deep Data Card

## Dataset
- Root: `/Users/charan/Desktop/Masters RCA/datasets/RCAEval`
- Cases: **30**
- Faults: `{'f3': 6, 'f4': 6, 'f5': 6, 'f1': 9, 'f2': 3}`
- Services: `{'adservice': 9, 'cartservice': 3, 'currencyservice': 3, 'emailservice': 15}`

## Telemetry profile
- Avg metric columns / case: **70.3**
- Avg sampling interval: **1.00s**
- Avg missing rate: **0.0336**
- Avg constant metric columns: **12.7**
- Avg log lines: **69840**
- Avg traces: **158503**
- Mean |z| shift on true-service metrics (pre→post): **14330170.23**

## Cleaning decisions
- Drop constant / near-constant metric columns before ranking.
- Align all analysis to inject_time; use pre-window as baseline.
- Never put case folder names in model prompts (label leakage).
- Map metrics to services via known Online Boutique prefixes.
- Treat redis_* metrics as redis-cart in our dependency graph.

## Per-fault summary
See `re3ob_deep_eda_summary.json` → `by_fault`.

## Leakage
Case directory names encode root-cause service + fault. Use only as labels.
