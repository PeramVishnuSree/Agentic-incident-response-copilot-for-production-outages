# RCAEval RE2-OB — Complete Experiment Results

**Suite:** RE2 Online Boutique (90 labelled multi-source cases)  
**Data:** public RCAEval benchmark (not created by this team)  
**Date:** 2026-11-09  
**Command:** `make rcaeval-all` / `uv run python -m eval.rcaeval.run_all --suite re2ob`

---

## 1. Deep EDA (done)

| Check | Result |
|------|--------|
| Cases | 90 |
| Faults | cpu/mem/disk/delay/loss/socket × 15 each |
| Services | 5 services × 18 each |
| Avg metric columns | ~73 |
| Sampling interval | **1.0 s** |
| Avg missing rate | ~0.004 |
| Avg constant metric cols | ~15 (drop before ranking) |
| Avg log lines / case | ~167k |
| Avg traces / case | ~383k |
| Leakage | Folder names encode true service+fault — never put paths in prompts |

Artifacts:
- `re2ob_deep_data_card.md`
- `re2ob_deep_eda_summary.json`
- `re2ob_deep_eda_cases.csv`

---

## 2. Correlation window sweep (done)

Scored service anomaly magnitude inside post-inject windows  
`W ∈ {30, 60, 120, 300, 600, 900}` seconds.

| W (s) | AC@1 | AC@3 |
|------:|-----:|-----:|
| 30 | 0.800 | 0.978 |
| 60 | 0.833 | 0.989 |
| **120** | **0.833** | **1.000** |
| 300 | 0.733 | 1.000 |
| 600 | 0.722 | 0.989 |
| 900 | 0.700 | 0.978 |

**Chosen window: 120 seconds** (best AC@3, strong AC@1; matches our design default).

---

## 3. Learned ranker (done)

Gradient-boosted classifier on features:
`anomaly_score`, `onset_sec`, `upstreamness`, `log_error_rate`, `n_metrics`  
Cross-validation: GroupKFold by case (5 folds).

| Metric | Score |
|--------|------:|
| AC@1 | **0.900** |
| AC@3 | **0.978** |

Feature importance (approx): anomaly_score **87%**, onset **8%**, log_error_rate **5%**.

---

## 4. BARO baseline (done)

Official RCAEval BARO on the same 90 RE2-OB cases (metric RCA).

| Metric | Overall |
|--------|--------:|
| AC@1 | **0.300** |
| AC@3 | **0.922** |
| AC@5 | **1.000** |
| Avg@5 | **0.804** |

Per-fault AC@1 is high on disk (~0.87), weaker on cpu/delay/socket (~0.07).  
This is the reference for resetting our engineering targets (do not keep arbitrary 60%/85% without this context).

---

## 5. What this means for the professor questions

1. **AI/ML?** Yes — statistical anomaly RCA (BARO), learned ranker (GBT), plus our LLM investigation layer in the product.  
2. **EDA?** Yes — deep EDA + data card on RE2-OB.  
3. **Metrics validated?** Yes — BARO numbers above are the empirical baseline.  
4. **Window size?** **120 s**, chosen by labelled sweep.

---

## Reproduce

```bash
uv sync --dev
make rcaeval-all
# artifacts under eval/artifacts/rcaeval/
```

## Next (optional harder sets)

Same pipeline supports Sock Shop / Train Ticket:

```bash
uv run python -m eval.rcaeval.run_all --suite re2ss
uv run python -m eval.rcaeval.run_all --suite re2tt
```
