# CMPE 295A — Early Prototype

**Advisor presentation checklist**

| Requirement | How this prototype shows it |
|-------------|----------------------------|
| Core project functionality | Real RE2-OB incident → read-only Telemetry Access Layer → local Qwen agent with tools → playbook plan → human approve → allowlisted dry-run execute |
| Basis for 295B | Live kubectl executor, Postgres audit store, human TTRC study, harder datasets |
| Integration of each member’s work | Single `make prototype` path wires all three owners |
| Contribution of each member | Explicit stages below + code ownership |

## Quick demo (no cluster required)

**Best for advisor (web console):**

```bash
cd repo
uv sync --dev
mlx_lm.server --model mlx-community/Qwen3-4B-4bit --host 127.0.0.1 --port 8080   # for live runs
make web
# opens http://127.0.0.1:8090
```

Without the local model, "Replay recorded run" plays the saved Qwen3-4B
trajectory of the same case step by step.

**Incident console.** Pick an incident from the queue (30 real RE2-OB faults, one
per service × fault, shown only as `INC-24xx`). Numbered sections walk the
pipeline:
1. What broke: alert, top metric changes and error logs.
2. Service map from traces, with the agent's suspects highlighted.
3. Signal charts around the incident.
4. LLM investigation: live or replay, tool budget, and each step with its evidence id.
5. Root-cause report: ranked candidates and claims with evidence chips.
6. Playbook plan with policy checks and alternatives.
7. Approve or reject; the approval modal requires an operator id, a note and a confirmation.
8. Dry-run execution and recovery check. "Not recovered" or "reject" feeds back to the next candidate.
9. Audit trail, then reveal the ground truth next to the N-Sigma / CIRCA / RCD / BARO rankings.

**Evaluation** page: N1 baselines with CIs, agent vs baselines on the same 30
cases, agent runs, planner experiment, failure modes. **Architecture & flow**:
the two separate figures and the answers to the flow questions. **Team & safety**.

The earlier Streamlit console (`make prototype-ui`, port 8501) still works as a fallback.

CLI (same backend):

```bash
uv run pytest
make prototype                 # cpu-stress vertical path
make prototype-pod-crash       # second scenario
make prototype-feedback        # failed remedy → next candidate
```

Optional live fault injection (needs kind + Chaos Mesh):

```bash
make cluster-up && make target-app && make chaos-install
make scenario-cpu-stress
make scenario-pod-crash
```

## End-to-end flow

Real incident path (web console, main demo):

```
[RCAEval]  RE2-OB case (metrics, logs, traces) — clock = inject + 300 s (oracle onset)
     ↓
[Patrini]  RCAEvalReplay (TAL: anonymous id, no data after now)
           → Qwen3-4B ReAct agent, 3 read-only tools, ≤12 calls → top_services + cited claims
     ↓
[Peram]    Playbook planner → ApprovalGate (audit) → AllowlistedExecutor (dry-run)
```

Scripted path (CLI and the Streamlit fallback's "Scripted scenario"):

```
[Gandham]  Scenario ground truth → synthetic Event[] (gateway schema)
     ↓
[Patrini]  Correlation engine (graph + window + top-k) → RCA agent (mock LLM, read-only)
     ↓
[Peram]    Playbook planner → ApprovalGate (audit) → AllowlistedExecutor (dry-run)
```

## Team member contributions (early prototype)

### Charan Sai Gandham
- Telemetry **Event** schema + gateway collectors/normaliser (`services/telemetry-gateway/`)
- Kind / Online Boutique / Chaos Mesh deploy path (`deploy/`, `scenarios/`)
- Prototype signal synthesis from scenario ground truth (`console/cli/prototype.py` → `synthesize_signals`)
- Fault scenarios: `pod-crash`, `cpu-stress` (`scenarios/registry.yaml`)

### Venkata Satya Charan Naga Deep Patrini
- Dependency graph (`config/dependency-graph.yaml`)
- Correlation grouping + deterministic ranking (`services/correlation-engine/`)
- Read-only RCA agent + evidence verifier + mock LLM (`services/rca-agent/`)
- N1: official RCAEval baselines (BARO, N-Sigma, E-Diagnosis, CIRCA, multi-source BARO, RCD, PDiagnose) on RE2-OB with CIs; redis/0.30 gap explained (`docs/baselines.md`)
- N2: Telemetry Access Layer + RCAEval replay with leakage tests (`libs/telemetry_access/`)
- N3: OpenAI-compatible LLM client, 3 JSON-schema tools, bounded ReAct loop, real Qwen trajectories (`services/rca-agent/rca_agent/llm/`, `experiments/n3/`)

### Vishnu Sree Peram
- Remediation **playbook** planner (`services/remediation-planner/`)
- Human **approval** gate + audit log (`services/approval-service/`)
- Allowlisted **executor** dry-run (`services/executor/`)
- Vertical prototype wiring + feedback-loop demo (`console/cli/prototype.py`)
- Scenario registry ownership entries + eval harness direction

## Safety properties demonstrated

1. RCA path is read-only (no write tools).
2. No execute without approval record.
3. Executor rejects off-allowlist actions and off-allowlist namespaces.
4. Default mode is **dry-run** (no cluster mutation in the early prototype).
5. Failed remedy uses a **feedback loop** that still requires a new approval.

## What broadens in 295B

- Postgres-backed incident + audit store  
- Live kubectl allowlisted actions after approval  
- Hosted LLM bakeoff + ranking/LLM ablations  
- Human pilot (TTRC with vs without copilot)  
- Harder public datasets (OpenRCA / ORCA-bench / …)

## Advisor design package

See also `../295A_Design_Validation/295A_Design_and_Validation_Report.pdf` for architecture≠flow, surveys, and validation numbers.
