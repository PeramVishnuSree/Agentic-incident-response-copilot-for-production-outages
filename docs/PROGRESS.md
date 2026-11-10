# Project progress

**Project:** Agentic Incident-Response Copilot for Production Systems  
**Course:** CMPE 295A · Advisor: Dr. Bertin Cordova-Diba  
**Repo:** https://github.com/PeramVishnuSree/Agentic-incident-response-copilot-for-production-outages  
**Updated:** 2026-11-09

## Status

Early diagnosis pipeline is implemented in-repo: collectors, dependency-graph correlation, top-3 ranking, read-only RCA path with evidence checks, two Chaos Mesh scenarios, and RCAEval RE2-OB EDA. Live cluster bring-up uses `make cluster-up` / `make dev-up` on a machine with Docker and kind.

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
| Window sweep (chose **120s**) | `re2ob_window_sweep.json` |
| Learned GBT ranker (AC@1≈0.90) | `re2ob_ranker_summary.json` |
| BARO baseline on 90 OB cases | `re2ob_baro_summary.json` (AC@1=0.30, AC@3=0.92) |
| Baseline plan (BARO / HolmesGPT) | `docs/baselines.md` |
| Architecture notes | `docs/architecture.md` |

**Tests:** `uv run pytest` → 16 passing.  
**RCAEval report:** `eval/artifacts/rcaeval/re2ob_RESULTS.md`

---

## In progress / next

| Item | Notes |
|------|--------|
| PostgreSQL incident store | Next sprint |
| Approval API + restricted executor | Next sprints |
| Vertical demo (fault → diagnose → approve → recover) | Mid-semester demo |
| BARO numbers on RE2-OB | Experiment X1 |
| Human pilot study | Semester B |

---

## Demo commands

```bash
uv sync --dev
uv run pytest
make eda

# optional live cluster
make cluster-up && make target-app && make observability && make chaos-install
make scenario-pod-crash
make scenario-cpu-stress
```
