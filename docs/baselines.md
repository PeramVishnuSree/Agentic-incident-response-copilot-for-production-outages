# Baseline review (Patrini — Workbook 2 Sprint 2)

Notes toward the BARO / N-Sigma / E-Diagnosis / HolmesGPT comparisons.

## BARO (ESEC/FSE 2024)
- Multivariate Bayesian online change-point detection + robust statistical scoring for metric-based RCA.
- Role here: deterministic, LLM-free metric baseline for the correlation/ranking stage.
- **RE2-OB (our run, n=90):** AC@1 = 0.300 [0.211, 0.389], AC@3 = 0.922 [0.867, 0.978], Avg@5 = 0.804 [0.764, 0.840].
- Published reference: Avg@5 ≈ 0.86 on Online Boutique metric data (BARO repo); our RE2 multi-source suite lands nearby.

## N-Sigma / E-Diagnosis (RCAEval metric baselines)
- Ran on the same RE2-OB cases via `RCAEval.e2e`.
- **N-Sigma:** AC@1 = 0.856 [0.778, 0.922] — strong simple competitor on this suite.
- **E-Diagnosis:** AC@1 = 0.111 [0.056, 0.178] — weak on RE2-OB; kept as a lower reference.

## HolmesGPT (CNCF Sandbox)
- Open-source agentic Kubernetes troubleshooting tool. Closest open comparison system to this project.
- **Adapter plan:** live-cluster dry-run on Chaos Mesh scenarios (needs kind + app up).

## K8sGPT (cheap rules + LLM explanation baseline)
- Rule-based analyzers with LLM explanation only.
- Useful ablation: shows what “rules + LLM wording” gets without our correlation + evidence verifier.

## Scoring (validated)
- Metrics: AC@1 / AC@3 / AC@5 / Avg@5 with **bootstrap 95% CIs**.
- **Revised targets** replace workbook 60%/85% — see `eval/artifacts/rcaeval/METRICS_VALIDATION.md`.
- Reproduce: `make rcaeval-metrics-validation`

## Trial log (Sprint 2)
| Date | Action | Result |
|------|--------|--------|
| 2026-11-09 | Selected RCAEval as public evaluation corpus | RE2-OB = 90 labelled Online Boutique cases |
| 2026-11-09 | Documented BARO / HolmesGPT / K8sGPT roles | This file |
| 2026-11-09 | BARO on RE2-OB | AC@1=0.30, AC@3=0.92, Avg@5=0.80 |
| 2026-11-09 | N-Sigma + E-Diagnosis on RE2-OB | AC@1=0.856 / 0.111 |
| 2026-11-09 | Bootstrap CIs + revised targets + study size | `METRICS_VALIDATION.md` |
| TBD | HolmesGPT dry-run on pod-crash scenario | needs live cluster |
