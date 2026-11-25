# Naga Charan Patrini — Phase 0 tasks N1, N2, N3

Status against the roadmap's "done when" criteria, with the commands that
reproduce each artifact. Everything runs on an Apple Silicon laptop; nothing
needs the GPU cluster.

## N1 — Baselines reproduced, in one table

**Done when:** BARO on RE2-OB is within the paper's CI or the gap is explained
in writing, and all baselines are in one table. **Status: done.** The table and
explanation are in [`docs/baselines.md`](baselines.md).

- The official RCAEval checkout is pinned (`../external/RCAEval`, commit and
  dataset md5 in `eval/artifacts/rcaeval/official_runs/provenance.json`).
  Every method runs unmodified through upstream `main.py`; the script refuses to
  run if the checkout has local edits.
- Methods: BARO, multi-source BARO, N-Sigma, E-Diagnosis, CIRCA, RCD (Python 3.8
  env), random ranking, and PDiagnose. PDiagnose is not wired into upstream
  `main.py`, so `scripts/run_pdiagnose.py` ports the upstream implementation
  line by line.
- `eval/rcaeval/scoring.py` computes AC@1/3/5 and Avg@5 with bootstrap CIs per
  fault from the per-case rankings, and paired-bootstrap differences. Its
  Avg@5 equals upstream's printed numbers exactly for every method.
  *This is Vishnu's evaluation interface, implemented provisionally — please
  review.*
- The paper has no RE2-OB table (its Table 6 is RE2-TT), so the comparison
  target is upstream `main.py` on RE2-OB, which we match exactly.
- The 0.30 vs 0.14 gap and the redis hypothesis are tested in
  `eval/rcaeval/redis_hypothesis.py` (variants A0–F). See `docs/baselines.md`.
- `_prepare_metrics` in `eval/rcaeval/baselines.py` now mirrors upstream
  `main.py`, and the harness passes the `dataset` argument. It reproduces the
  official BARO AC@1 of 0.14 on the same 90 cases.

```bash
# one-time: official checkout + envs (see docs/baselines.md "Reproduce")
make rcaeval-official     # all methods, archived to eval/artifacts/rcaeval/official_runs/
make n1-report            # redis hypothesis + one table → eval/artifacts/rcaeval/n1/
```

## N2 — Telemetry Access Layer and replay

**Done when:** the protocol is implemented with a clock, no leakage, tests,
and CI. **Status: done.**

- `libs/telemetry_access/telemetry_access/protocol.py`: `TelemetrySource` with
  `now`, `metrics`, `logs`, `traces`, `topology`. `metrics` returns the shape of
  a Prometheus `query_range` response (`resultType: matrix`), so the live
  Prometheus backend in Phase 1 is a drop-in replacement.
- `RCAEvalReplay` clips every query to `now` and normalises s/ms/µs/ns
  timestamps. It maps log and trace rows to services and builds the call graph
  from parent/child spans seen before `now`. It returns a random
  `replay-<hex>` case id.
  The clock comes from an explicit timestamp or an onset detector; the default
  is the oracle `inject_time + 300 s`, recorded in `clock_source`.
- Leakage tests (`libs/telemetry_access/tests/test_leakage.py`) run on real
  RE2-OB cases. They check that no data after `now` is returned and that the
  output never contains the case name, path, service/fault label, "inject", or
  forbidden keys. They also check that ids are random and that `now` differs
  from the injection time. The tests skip when the dataset is absent.
- `telemetry-access` is a uv workspace member and runs in CI with
  `uv run pytest`.

## N3 — Local open-weight model, tools, bounded ReAct

**Done when:** 5 RE2-OB trajectories are saved as JSON and half a page of
failure-mode notes is written. **Status: done**, plus a 30-case run and a
second model.

- `rca_agent/llm/vllm_client.py`: OpenAI-compatible client (vLLM, MLX-LM,
  Ollama). MockLLM is kept for CI.
- `rca_agent/tools/telemetry.py`: JSON-schema tools `get_metrics`,
  `search_logs` and `get_topology` over the TAL. They return compact
  window-versus-baseline summaries and validate their arguments.
- `rca_agent/llm/react_loop.py`: bounded loop (12 tool calls). Output is
  `{top_services, claims: [{service, claim, evidence_refs}]}` with evidence ids
  E1..En, one repair turn, and a forced answer when the budget runs out. Every
  step is recorded.
- Trajectories: `experiments/n3/trajectories/<run>/case_*.json`, scored by our
  code and by RCAEval's `rcaeval-agent evaluate`
  (`<run>/rcaeval_official/`).
- Failure modes: [`experiments/n3/FAILURE_MODES.md`](../experiments/n3/FAILURE_MODES.md).

```bash
mlx_lm.server --model mlx-community/Qwen3-4B-4bit --host 127.0.0.1 --port 8080
ollama serve   # optional: ollama pull qwen2.5:7b-instruct
make n3-smoke
```

## Prototype integration

The web console (`make web`, http://127.0.0.1:8090) runs a real RE2-OB incident
through the TAL and the agent, then through the existing planner, approval gate
and dry-run executor (Streamlit fallback: `make prototype-ui`). See
`docs/EARLY_PROTOTYPE.md`.

Planner experiment on the 30 agent diagnoses: `uv run python -m eval.planner_eval`.
First plan targets the true service in 93% of cases; the fault-family rule is
right in 57% (resource-first; 52% over all 90 cases); the feedback loop
resolves every case within three approvals.

## Known limits

- All agent and baseline numbers use the oracle onset; the detected onset (C1)
  is the next re-run.
- Evidence references are checked for existence only. Semantic verification is
  Phase 1.
- 30 cases is a small sample: the agent's lead over N-Sigma is not
  statistically significant.
