# Baseline review (S1 — Patrini)

Notes toward the BARO and HolmesGPT comparisons (desired requirement; run in S8).

## BARO
- Multivariate Bayesian online change-point detection + robust statistical
  scoring for metric-based RCA (ESEC/FSE 2024).
- Role here: deterministic, LLM-free metric baseline for the correlation/ranking
  stage. Fast and inspectable.
- TODO: adapter under `eval/baselines/baro/` that consumes our common Event
  schema and emits ranked candidates.

## HolmesGPT
- Open-source agentic Kubernetes troubleshooting tool (CNCF). Closest open
  comparison system to this project.
- Role here: end-to-end agent baseline for diagnosis quality and time.
- TODO: adapter under `eval/baselines/holmesgpt/`; run against the same frozen
  scenario suite and score with the shared harness.

## Scoring (shared with the copilot)
Time to root cause, top-1 / top-3 accuracy, remediation outcome — see
workbook §2.1 targets. Baselines must run on identical scenarios and ground
truth for a fair comparison.
