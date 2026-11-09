# Baseline review (Patrini — Workbook 2 Sprint 2)

Notes toward the BARO and HolmesGPT comparisons (desired requirement; scored runs in S8).

## BARO (ESEC/FSE 2024)
- Multivariate Bayesian online change-point detection + robust statistical scoring for metric-based RCA.
- Role here: deterministic, LLM-free metric baseline for the correlation/ranking stage. Fast and inspectable.
- Public numbers (from paper / RCAEval): strong on Online Boutique resource faults; weaker on some network faults.
- **Our use:** run via the RCAEval harness on RE2-OB (experiment X1) before freezing Acc@1 / Acc@3 targets.
- **Adapter plan:** `eval/baselines/baro/` consuming normalised metrics and emitting ranked candidates in our `Candidate` schema.

## HolmesGPT (CNCF Sandbox)
- Open-source agentic Kubernetes troubleshooting tool. Closest open comparison system to this project.
- Role here: end-to-end agent baseline for diagnosis quality and time on the same Chaos Mesh scenarios.
- **Adapter plan:** `eval/baselines/holmesgpt/`; score with the shared harness (top-1 / top-3 / TTRC).

## K8sGPT (cheap rules + LLM explanation baseline)
- Rule-based analyzers with LLM explanation only.
- Useful ablation: shows what “rules + LLM wording” gets without our correlation + evidence verifier.

## Scoring (shared with the copilot)
Time to root cause, top-1 / top-3 accuracy, remediation outcome — see workbook §2.1 targets. Baselines must run on identical scenarios and ground truth for a fair comparison.

## Trial log (Sprint 2)
| Date | Action | Result |
|------|--------|--------|
| 2026-11-09 | Selected RCAEval as public evaluation corpus | RE2-OB = 90 labelled Online Boutique cases |
| 2026-11-09 | Documented BARO / HolmesGPT / K8sGPT roles | This file |
| TBD | Install BARO + reproduce RE2-OB AC@1 | X1 |
| TBD | HolmesGPT dry-run on pod-crash scenario | needs live cluster |
