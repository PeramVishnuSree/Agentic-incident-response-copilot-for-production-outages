# RCAEval — All Suites Results

Data root: `/Users/charan/Desktop/Masters RCA/datasets/RCAEval`

| Suite | Cases | Window | Ranker AC@1 | Ranker AC@3 | BARO AC@1 | BARO AC@3 | BARO Avg@5 |
|------|------:|-------:|------------:|------------:|----------:|----------:|-----------:|
| re1ob | 125 | 30s | 0.772 | 0.951 | 0.216 | 0.840 | 0.696 |
| re1ss | 125 | 120s | 0.880 | 0.992 | 0.352 | 0.912 | 0.794 |
| re1tt | 125 | 60s | 0.560 | 0.888 | 0.120 | 0.416 | 0.373 |
| re2ob | 90 | 120s | 0.889 | 0.978 | 0.300 | 0.922 | 0.804 |
| re2ss | 90 | 60s | 0.922 | 0.989 | 0.111 | 0.822 | 0.691 |
| re2tt | 90 | 60s | 0.633 | 0.867 | 0.422 | 0.678 | 0.638 |
| re3ob | 30 | 60s | 0.967 | 1.000 | 0.000 | 0.900 | 0.713 |
| re3ss | 30 | 120s | 0.667 | 0.967 | 0.067 | 0.633 | 0.513 |
| re3tt | 30 | 120s | 0.833 | 0.867 | 0.233 | 1.000 | 0.807 |

## Notes
- RE1 is metrics-only (no logs/traces).
- RE2/RE3 include multi-source telemetry where available.
- Per-suite deep data cards and JSON live under `eval/artifacts/rcaeval/`.

## Reproduce
```bash
uv run python -m eval.rcaeval.run_all_suites
```
