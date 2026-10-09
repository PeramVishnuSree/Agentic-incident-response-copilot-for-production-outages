# eval (Peram — built from S4, runs S10–S11)

Evaluation harness for the manual-vs-copilot comparison (E12, workbook Ch 9).
- `harness/` — run orchestration and timers.
- `scoring/` — time to root cause, top-1 / top-3 accuracy, remediation outcome,
  latency, cost, unsafe-action rate.
- `baselines/` — BARO and HolmesGPT adapters (see `../docs/baselines.md`).
- `notebooks/` — analysis and the results report.
- `runs/` — raw run artifacts (git-ignored; track with DVC/Git-LFS).
