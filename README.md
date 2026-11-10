# Agentic Incident-Response Copilot for Production Outages

A human-supervised copilot for Kubernetes microservice outages. It collects telemetry, groups related symptoms, ranks likely root causes with checkable evidence, drafts a remediation plan, and **never changes the cluster until an operator approves**.

**CMPE 295** master’s project · San José State University  
**Team:** Charan Sai Gandham · Venkata Satya Charan Naga Deep Patrini · Vishnu Sree Peram  
**Advisor:** Dr. Bertin Cordova-Diba

---

## What it does

When a service fails in production, alerts, metrics, logs, and events all fire at once. Operators waste time chasing symptoms instead of the real cause.

This project builds a measurable pipeline that:

1. **Ingests** metrics, logs, Kubernetes events, and alerts into one schema  
2. **Correlates** related signals with a time window + service dependency graph  
3. **Ranks** top root-cause candidates (works even if the LLM is down)  
4. **Investigates** with read-only tools and cites evidence that must exist in stored data  
5. **Proposes** a structured fix (action, risk, undo)  
6. **Waits for human approval**, then runs only allowlisted actions through a restricted executor  

Evaluation uses a local Online Boutique + Chaos Mesh testbed **and** the public **RCAEval** benchmark (not a hand-made dataset).

---

## Architecture

```
Telemetry → gateway / normaliser → incident store
        → deterministic correlation (group + rank)
        → read-only RCA agent (evidence + explanation)
        → remediation plan
        → human approval
        → restricted executor   ← only write path
```

Full detail: [docs/architecture.md](docs/architecture.md) · safety / baselines: [docs/baselines.md](docs/baselines.md) · status: [docs/PROGRESS.md](docs/PROGRESS.md)

---

## Repository layout

```text
libs/common/              Shared Event / Candidate schema and config
services/
  telemetry-gateway/      Collect + normalise telemetry
  correlation-engine/     Time-window + dependency-graph grouping & ranking
  rca-agent/              Read-only RCA agent + model-agnostic LLM interface
  remediation-planner/    Drafts plans only (later sprint)
  approval-service/       Human approval gate + audit log (later sprint)
  executor/               ONLY write path; allowlisted actions (later sprint)
config/                   Online Boutique dependency graph
deploy/                   kind, Online Boutique, Prometheus, Chaos Mesh
scenarios/                Fault suite with ground truth (pod-crash, cpu-stress, …)
eval/                     EDA, scoring harness, baseline notes
docs/                     Architecture, baselines, progress
console/                  Operator console (CLI first, UI later)
```

---

## Current status

| Area | Status |
|------|--------|
| Shared event schema + CI | Done |
| Telemetry collectors / normaliser / in-memory store | Done |
| Dependency graph + incident grouping + top-3 ranking | Done |
| Read-only RCA tools, evidence verifier, mock LLM + spend cap | Done |
| Fault scenarios: pod-crash, cpu-stress | Done |
| RCAEval RE2-OB deep EDA + window sweep + GBT ranker + BARO | Done (`make rcaeval-all`) |
| PostgreSQL store, approval UI, restricted executor | In progress (next sprints) |
| Human pilot study | Planned (Semester B) |

Unit tests: **16 passing** (`uv run pytest`).  
RCAEval results: [`eval/artifacts/rcaeval/re2ob_RESULTS.md`](eval/artifacts/rcaeval/re2ob_RESULTS.md).

---

## Quick start

### Prerequisites

- [uv](https://docs.astral.sh/uv/)
- Docker, [kind](https://kind.sigs.k8s.io/), `kubectl`, Helm (for the live testbed)

### Install and test

```bash
git clone https://github.com/PeramVishnuSree/Agentic-incident-response-copilot-for-production-outages.git
cd Agentic-incident-response-copilot-for-production-outages

uv sync --dev
uv run pytest
```

### RCAEval experiments (public benchmark)

Place RE2 cases under `../datasets/RCAEval` (or set `RCAEVAL_DIR`), then:

```bash
make rcaeval-all
# deep EDA + window sweep + learned ranker + BARO baselines
# → eval/artifacts/rcaeval/re2ob_RESULTS.md
```

### Local Kubernetes testbed

```bash
cp .env.example .env   # add LLM key; keep the per-run spend cap

make cluster-up        # kind cluster
make target-app        # Online Boutique
make observability     # Prometheus + Alertmanager
make chaos-install     # Chaos Mesh

make scenario-pod-crash
make scenario-cpu-stress

make dev-down          # teardown
```

Run `make help` for all targets.

---

## Team ownership

| Member | Focus |
|--------|--------|
| **Charan Sai Gandham** | Cluster, observability, telemetry gateway, collectors |
| **Venkata Satya Charan Naga Deep Patrini** | Correlation engine, RCA agent, shared schema, baselines |
| **Vishnu Sree Peram** | Fault scenarios, remediation, approval path, evaluation |

---

## Safety principles

- Diagnosis tools are **read-only** (enforced in CI).  
- The executor is the **only** write path.  
- Every write requires a recorded human approval.  
- Only allowlisted actions / namespaces are permitted.  
- Correlation still returns a result if the LLM is unavailable.

---

## License / academic use

Built for CMPE 295 at SJSU. Evaluation data includes the public [RCAEval](https://github.com/phamquiluan/RCAEval) benchmark — cite the original authors when reporting results.
