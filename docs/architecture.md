# Architecture

Telemetry flows from the target cluster through collectors and a normaliser into
an incident store. The correlation engine groups signals using time windows and
the service dependency graph. The RCA agent queries stored data and read-only
Kubernetes endpoints, then produces ranked candidates with cited evidence. The
remediation planner drafts a structured plan; a human operator can approve,
edit, or reject it. **Only the restricted executor can write to the cluster, and
only allowlisted actions in allowlisted namespaces.**

```
 target cluster ─▶ telemetry-gateway ─▶ incident store (PostgreSQL)
 (Online Boutique)   (collectors +            │
  + Chaos Mesh)        normaliser)            ▼
                                        correlation-engine ─▶ ranked candidates
                                                 │
                                                 ▼
                                             rca-agent  (read-only tools)
                                                 │  candidates + evidence
                                                 ▼
                                        remediation-planner (plan + risk + undo)
                                                 │
                                                 ▼
                                          human approval  ──▶  restricted-executor
                                            (audit log)        (ONLY write path)
```

## Safety boundary (the testable property)

Diagnosis is separated from execution. No diagnosis component (gateway,
correlation engine, RCA agent, planner) has a write path to the cluster. This
is enforced structurally and checked in CI — see
`services/rca-agent/tests/test_tools_readonly.py`. Graceful degradation: the
deterministic correlation result remains available even if the LLM is down.

## Component ownership

| Component | Owner | First sprint |
|-----------|-------|--------------|
| telemetry-gateway, deploy/, scenarios/ | Gandham | S1–S2 |
| correlation-engine, rca-agent, libs/common | Patrini | S1–S3 |
| remediation-planner, approval-service, executor, console, eval | Peram | S3, S1 (chaos) |

See the workbook for the full S1–S12 schedule and requirements (E1–E13).
