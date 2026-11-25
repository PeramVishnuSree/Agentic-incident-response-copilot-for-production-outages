# CMPE 295A response: evidence, planning, feedback, and demo

This document responds to the advisor's request for a separate architecture,
an explicit processing flow, preliminary evidence, and a closed-loop operator
experience. It is the 295A boundary: the system is read-only and simulated at
the approval boundary; production remediation belongs to 295B.

## 1. System architecture versus processing flow

### System architecture (what exists and where it runs)

```text
target cluster
  -> telemetry gateway / normalizer
  -> incident store
  -> correlation engine
       - time-window grouping
       - dependency graph
       - deterministic candidate ranking
  -> read-only RCA agent
       - metrics, logs, topology tools
       - evidence verifier
       - bounded model calls
  -> remediation planner
  -> operator console / approval service
  -> restricted executor (295B; only write path)
```

The LLM is not the source of truth and never has a cluster write tool. The
correlation engine always produces a deterministic result if the LLM is down.
The console's approval endpoint records a simulated approval and explicitly
reports `cluster_write_performed: false`.

### Processing flow (what happens for one incident)

1. Normalize raw signals into the shared `Event` schema.
2. Group signals within a 120-second window when services are connected in the
   dependency graph.
3. Rank the top-k services using severity, upstreamness, and onset precedence.
4. Attach evidence references to every candidate.
5. Convert confidence into a planner policy:
   - high confidence: one primary remedy plus a low-risk verification step;
   - medium confidence: collect more evidence; do not suggest a write;
   - low confidence: stop automation and request human investigation.
6. Show the operator the candidate, uncertainty, evidence, risk, and undo plan.
7. Require explicit approval before a simulated remedy transition.
8. Verify the outcome. If unresolved, increment the attempt counter, collect new
   evidence, and re-rank instead of repeating the same action blindly.

## 2. Planner decision policy

The planner does not map every top-k candidate to an independent destructive
action. It selects one primary hypothesis and may add one low-risk evidence or
verification action.

| Confidence | Planner output | Write allowed? |
|---|---|---|
| >= 0.75 | Primary remedy + verification step | Only after approval |
| 0.50–0.749 | Evidence collection / diagnosis refinement | No |
| < 0.50 | Human investigation request | No |

The confidence shown in the demo is a ranking confidence, not a probability of
truth. Calibration is a 295A experiment: reliability diagrams, Brier score,
expected calibration error, and selective accuracy at coverage levels will be
reported before treating it as a probability.

## 3. Feedback loop

The operator has three outcomes: `resolved`, `unresolved`, and
`more_evidence`. An unresolved outcome creates a new investigation state,
records the failed attempt, and prevents a blind repeat. In 295B this state will
be persisted in the incident store and used for policy/ranker improvement; it
will not be used as unreviewed online self-training.

## 4. Preliminary evidence already available

The public RCAEval benchmark contains 735 labelled cases; RE2-OB contains 90
multi-source Online Boutique cases. Current local evidence includes:

- EDA and leakage controls in `EDA/RCAEval_EDA_SUMMARY.md`;
- a 120-second post-injection window selected by a RE2-OB sweep;
- official RCAEval `main.py` runs of BARO, N-Sigma, E-Diagnosis, multi-source
  BARO, CIRCA and RCD, plus a port of PDiagnose, on all 90 RE2-OB cases, in one
  table with 95% CIs (`docs/baselines.md`);
- real local-LLM agent trajectories (Qwen3-4B, qwen2.5-7b) on RE2-OB, scored
  by RCAEval's own `rcaeval-agent evaluate` (`experiments/n3/`);
- unit tests covering grouping, ranking, evidence, read-only tools, replay
  leakage, and the agent loop.

The raw results are in `eval/artifacts/rcaeval/` and must be reported with the
dataset split, preprocessing version, and confidence intervals.

## 5. Component evaluation plan

| Component | Question | Primary metric | Experiment |
|---|---|---|---|
| Correlation | Does grouping combine a cascade without merging unrelated incidents? | pairwise precision/recall, incident F1, onset error | window sweep: 30/60/120/300s; graph on/off |
| Ranker | Does top-k identify the root-cause service? | AC@1, AC@3, AC@5, MRR, Avg@5 | BARO, N-Sigma, CIRCA, PDiagnose, GBT; leave-one-system-out |
| Evidence verifier | Are claims grounded in returned telemetry? | citation precision, unsupported-claim rate, tool error rate | adversarial missing/contradictory evidence cases |
| Planner | Does confidence produce a safe action policy? | unsafe recommendation rate, abstention precision, plan validity | confidence thresholds and remedy policy ablation |
| Agent | Does the model use tools efficiently? | task success, tool-call count, invented-tool rate, loop rate | 5-case smoke first; then 30/90-case trajectory study |
| End-to-end | Does the copilot improve diagnosis without unsafe writes? | time-to-correct-diagnosis, AC@k, calibration, approval burden | deterministic, agent, and human-assisted conditions |

## 6. AI/SRE literature and model-selection work package

The survey will be organized around four questions requested by the advisor:

1. AI for SRE: anomaly detection, metric/log/trace correlation, incident
   summarization, and root-cause ranking.
2. Model families: small open instruct models, reasoning models, and tool-use
   models, compared on tool-call validity, latency, memory, and diagnosis
   accuracy—not only generic benchmarks.
3. Fine-tuning: start with prompting and structured tool schemas; then compare
   supervised fine-tuning on verified trajectories with preference/feedback
   tuning only after a safe trajectory dataset exists. No production data is
   used without redaction.
4. Agentic workflows: compare a single-pass model with bounded ReAct/tool use,
   evidence verification, and planner feedback. The key hypothesis is that
   tool-grounded bounded interaction improves evidence quality, while loops and
   overconfidence are failure modes to measure.

The model selection rule is therefore empirical: choose the smallest open model
that meets minimum tool-call validity, evidence-grounding, latency, and
calibration thresholds on held-out RCAEval cases. A larger reasoning model is
not selected merely because it produces longer explanations.

## 7. Local demo

Install the console dependencies and start it from the repository root:

```bash
uv sync --dev
mlx_lm.server --model mlx-community/Qwen3-4B-4bit --port 8080   # optional, for live agent runs
make web
```

Open `http://127.0.0.1:8090`. The incident console replays a real RE2-OB
incident through the Telemetry Access Layer, runs the local Qwen agent (or
replays its saved trajectory), and continues through the playbook plan, human
approval, dry-run execution and the failed-remedy feedback loop before
revealing the ground truth next to the baselines. The Evaluation page carries
the N1, N3 and planner numbers. Steps are described in `docs/EARLY_PROTOTYPE.md`.

The Streamlit console (`make prototype-ui`, port 8501) is kept as a fallback.
