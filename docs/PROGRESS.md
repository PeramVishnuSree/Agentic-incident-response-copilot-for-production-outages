# Project progress

**Project:** Agentic Incident-Response Copilot for Production Systems  
**Course:** CMPE 295A · Advisor: Dr. Bertin Cordova-Diba  
**Repo:** https://github.com/PeramVishnuSree/Agentic-incident-response-copilot-for-production-outages  
**Updated:** 2026-11-09

## Status

Early diagnosis pipeline is implemented in-repo: collectors, dependency-graph correlation, top-3 ranking, read-only RCA path with evidence checks, two Chaos Mesh scenarios, and full RCAEval (RE1/RE2/RE3 × OB/SS/TT, 735 cases). Live cluster bring-up uses `make cluster-up` / `make dev-up` on a machine with Docker and kind.

---

## Completed

| Item | Evidence |
|------|----------|
| Shared Event / Candidate schema | `libs/common/` |
| CI (lint + unit tests) | `.github/workflows/ci.yml` |
| Telemetry gateway, collectors, normaliser, in-memory store | `services/telemetry-gateway/` |
| Online Boutique dependency graph | `config/dependency-graph.yaml` |
| Incident grouping + deterministic top-3 ranking | `services/correlation-engine/` |
| Read-only RCA tools + evidence verifier + mock LLM / spend cap | `services/rca-agent/` |
| Fault scenarios: pod-crash, cpu-stress | `scenarios/` |
| RCAEval RE2-OB deep EDA + data card | `make rcaeval-all` → `eval/artifacts/rcaeval/` |
| Window sweep (RE2-OB chose **120s**) | `re2ob_window_sweep.json` |
| Learned GBT ranker (RE2-OB AC@1≈0.89) | `re2ob_ranker_summary.json` |
| BARO baseline on 90 OB cases | `re2ob_baro_summary.json` (AC@1=0.30, AC@3=0.92) |
| Full RCAEval all 9 suites (735 cases) | `make rcaeval-everything` → `ALL_SUITES_RESULTS.md` |
| Metrics validation (baselines + bootstrap CIs + revised targets + study size) | `make rcaeval-metrics-validation` → `METRICS_VALIDATION.md` |
| Baseline plan (BARO / N-Sigma / HolmesGPT) | `docs/baselines.md` |
| Architecture notes | `docs/architecture.md` |

**Tests:** `uv run pytest` → 16 passing.  
**RCAEval report:** `eval/artifacts/rcaeval/ALL_SUITES_RESULTS.md`  
**Professor item #3 (metrics validated):** `eval/artifacts/rcaeval/METRICS_VALIDATION.md`  
**Full plain-English explainer (architecture + RCAEval + methods):** `docs/COMPLETE_EXPLAINER.md`

---

## In progress / next

| Item | Notes |
|------|--------|
| PostgreSQL incident store | Next sprint |
| Approval API + restricted executor | Next sprints |
| Vertical demo (fault → diagnose → approve → recover) | Mid-semester demo |
| Human pilot study | Semester B |

---

## Demo commands

```bash
uv sync --dev
uv run pytest
make eda
make rcaeval-everything
make rcaeval-metrics-validation

# optional live cluster
make cluster-up && make target-app && make observability && make chaos-install
make scenario-pod-crash
make scenario-cpu-stress
```
