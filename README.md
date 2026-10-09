# Agentic-incident-response-copilot-for-production-outages

An agent that watches logs/metrics/alerts (simulate with real open datasets or a Kubernetes test cluster you break on purpose), correlates signals across services, proposes root cause, and drafts the fix or rollback - with a human approving each step.

CMPE 295 master's project — Charan Sai Gandham, Venkata Satya Charan Naga Deep Patrini, Vishnu Sree Peram. Advisor: Dr. Bertin Cordova-Diba.

## Architecture (one line)

Telemetry → gateway/normaliser → incident store → deterministic correlation →
read-only RCA agent (ranked candidates + evidence) → remediation plan → **human
approval** → restricted executor (the only write path). See
[docs/architecture.md](docs/architecture.md).

## Repository layout

```
libs/common/            Shared event schema, config, DB models (the contract)
services/
  telemetry-gateway/    Collect + normalise telemetry (Gandham)
  correlation-engine/   Time-window + dependency-graph grouping & ranking (Patrini)
  rca-agent/            Read-only RCA agent + model-agnostic LLM interface (Patrini)
  remediation-planner/  Drafts plans only (Peram, S3)
  approval-service/     Human approval gate + audit log (Peram, S3)
  executor/             ONLY write path; allowlisted actions (Peram, S4)
console/                CLI (MVP) / React approval UI (Peram)
deploy/                 kind cluster, Online Boutique, observability, Chaos Mesh (Gandham)
scenarios/              Fault suite with known ground truth (Peram)
eval/                   Manual-vs-copilot evaluation harness (Peram)
```

## Getting started (Sprint 1)

Prerequisites: [uv](https://docs.astral.sh/uv/), Docker, `kind`, `kubectl`, `helm`.

```bash
# 1. Python workspace
uv sync --dev
uv run pytest            # schema + read-only-tool safety tests should pass

# 2. Local testbed
make cluster-up          # kind cluster
make target-app          # Online Boutique
make observability       # Prometheus + Alertmanager (+ Grafana)
make chaos-install       # Chaos Mesh

# 3. First fault scenario (pod-crash, with ground truth)
make scenario-pod-crash

# teardown
make dev-down
```

Run `make help` for all targets. Copy `.env.example` to `.env` and fill in your
LLM key (keep the per-run spend cap).

## Sprint 1 ownership

- **Gandham** — `deploy/` (kind, Online Boutique, Prometheus/Alertmanager), `services/telemetry-gateway/`.
- **Patrini** — repo/CI/tooling, `libs/common` schema, `services/rca-agent/` model interface + read-only tool stubs, baseline review ([docs/baselines.md](docs/baselines.md)).
- **Peram** — Chaos Mesh + first `scenarios/pod-crash` scenario.

## Meeting logs

Advisor and team meeting logs are in [`meetings/`](meetings/).
