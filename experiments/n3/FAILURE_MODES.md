# N3 failure-mode notes

Runs: Qwen3-4B-4bit (MLX, Apple Silicon) with prompt v1 and v2 on the 5 roadmap
cases, Qwen3-4B v2 on 30 RE2-OB cases (one per service x fault), and
qwen2.5-7b-instruct (Ollama) v2 on the 5 cases. All 4 runs were scored by
RCAEval's `rcaeval-agent evaluate`, which matches our own scores exactly.

| Run | Cases | AC@1 | AC@3 | Tool calls | Invalid | s / case |
|---|---:|---:|---:|---:|---:|---:|
| Qwen3-4B, prompt v1 | 5 | 0.20 | 0.20 | 35 | 0 | 7.6 |
| Qwen3-4B, prompt v2 | 5 | 0.80 | 1.00 | 25 | 0 | 8.2 |
| Qwen3-4B, prompt v2 | 30 | 0.93 | 1.00 | 152 | 0 | 8.3 |
| qwen2.5-7b, prompt v2 | 5 | 0.60 | 1.00 | 20 | 0 | 10.6 |

**Invalid tool calls, invented metric names, loops.** None were observed across
232 calls: there were no schema errors, unknown services, repeated identical
calls or parse repairs, and no run hit the 12-call budget (4–7 calls per case).
Two design choices keep this rate low, so it should not be read as a property of
the model. The tools take a *service*, not a metric name, so the model cannot
invent metric names. Their outputs are also small, pre-aggregated summaries.

**Anchoring without an overview (prompt v1).** With the plain prompt, Qwen3-4B
ran the same seven-call script on every case. It queried redis-cart,
checkoutservice and cartservice (the services that the prompt's service list
and topology made salient), then answered with those three. It never asked for
the cross-service overview and never looked at the faulty service. It also
chose a 60-second window. Because the clock is 300 s after onset, both the
window and its baseline lie inside the fault, so every z-score was near 0
(for example, cartservice_cpu z=1.9) and the model rationalised noise. Prompt v2
adds one procedure (overview first over −600..0, then drill down, then topology).
With it, all 40 v2 trajectories opened with the overview and used a 600 s window.

**Wrong answers: caller vs. callee.** The remaining v2 misses are the
productcatalogservice delay and loss faults. Recommendationservice calls
productcatalogservice, and both show huge latency increases (loss case:
productcatalogservice_latency-90 z≈34,000 vs. recommendationservice z≈31,500).
In both cases the model ranked the caller first. In the delay case its own
claim even says the callee "is a downstream service with high latency"
(the reason for blaming it) yet it is ranked second. In the loss case it calls
the top-scoring metric a "moderate increase". The evidence references exist,
but the claims misread them. qwen2.5-7b additionally blamed frontend for a
currencyservice delay.

**What these numbers do not show.**

- `unsupported_claims = 0` only means that every cited evidence id exists. It
  does not mean the claim matches the evidence, as the examples above show. A
  semantic evidence verifier is Phase 1 work.
- The clock is the oracle injection time + 300 s, so all numbers are upper
  bounds until the detected onset (C1) replaces it.
- Prompt v2 was written after reading the 5 v1 trajectories, so the 5-case v2
  score is tuned on its own test cases. The 30-case run (25 unseen cases) is the
  fairer estimate. On the same 30 cases, N-Sigma scores AC@1 0.83, and the gap
  is not statistically significant (see `docs/baselines.md`).
- A tool bug found during these runs: a constant baseline (for example
  redis_diskio = 0) produced z = 10⁶ and distorted the overview. The z-score now
  floors the scale at 1% of the baseline mean. Runs from before the fix are in
  `archive_tool_v1/` (30-case AC@1 was also 0.93; it missed productcatalogservice loss and
  currencyservice loss).
- Runs used Qwen3 with `/no_think`, temperature 0, on a Mac via MLX/Ollama
  rather than the vLLM Slurm job. The client is the same OpenAI-compatible
  adapter, and MockLLM remains in CI.
