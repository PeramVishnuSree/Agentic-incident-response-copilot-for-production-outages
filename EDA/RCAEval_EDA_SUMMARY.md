# RCAEval EDA Summary

**Notebook:** [`RCAEval_EDA.ipynb`](RCAEval_EDA.ipynb)  
**Project:** Agentic Incident-Response Copilot (CMPE 295)  
**Dataset:** public [RCAEval](https://github.com/phamquiluan/RCAEval) benchmark (not created by this team)  
**Date:** 2026-11-12

---

## 1. What we analyzed

RCAEval is a labelled microservice root-cause benchmark. We explored all **9 suites** available locally:

| Release | Meaning | Apps |
|---------|---------|------|
| **RE1** | Mostly metrics-only | Online Boutique (OB), Sock Shop (SS), Train Ticket (TT) |
| **RE2** | Metrics + logs/traces (when present) | OB, SS, TT |
| **RE3** | Functional / code-style faults (`f1`–`f5`) | OB, SS, TT |

**Total cases in our local copy: 735**  
(RE1: 125×3, RE2: 90×3, RE3: 30×3)

Each case folder name encodes the ground-truth label:

`{suite}_{service}_{fault}_{rep}`  
Example: `re2ob_checkoutservice_cpu_1` → suite=re2ob, service=checkoutservice, fault=cpu.

---

## 2. What’s inside one case

| File | Role |
|------|------|
| `metrics.parquet` | Time-series metrics; columns like `checkoutservice_cpu`, `cartservice_latency-90` |
| `logs.parquet` | Container logs (mainly RE2/RE3) |
| `traces.parquet` | Distributed traces (when available) |
| `inject_time.txt` | Timestamp when the fault starts |

**Column → service mapping:** strip known suffixes (`_cpu`, `_mem`, `_latency-90`, `_diskio`, `_socket`, `_error`, …).  
`redis_*` maps to `redis-cart` for Online Boutique naming.

---

## 3. Fault types

**RE1 / RE2 resource & network faults**

- `cpu`, `mem`, `disk`, `delay`, `loss`  
- `socket` (RE2 only)

**RE3 functional faults**

- `f1` … `f5` (OB has f1–f5; SS/TT in our download have f1–f4)

---

## 4. Key EDA findings

### Inventory (from notebook run)

| Suite | Cases | Avg metric cols | Avg logs | Avg traces | Missing rate |
|-------|------:|----------------:|---------:|-----------:|-------------:|
| re1ob | 125 | 54.4 | 0 | 0 | 0.0006 |
| re1ss | 125 | 59.0 | 0 | 0 | 0.0020 |
| re1tt | 125 | 213.6 | 0 | 0 | 0.0071 |
| re2ob | 90 | 73.4 | 167258 | 382903 | 0.0039 |
| re2ss | 90 | 76.6 | 84069 | 0 | 0.0086 |
| re2tt | 90 | 362.1 | 233467 | 748278 | 0.0051 |
| re3ob | 30 | 70.3 | 69840 | 158503 | 0.0336 |
| re3ss | 30 | 83.0 | 76608 | 0 | 0.0090 |
| re3tt | 30 | 315.2 | 54262 | 138423 | 0.0633 |

- All 9 suite folders parse cleanly with the naming regex above.
- RE1 cases have **no logs/traces** (metrics-only), matching the release design.
- Train Ticket suites have much wider metric tables → harder ranking problem.

### Data quality
- Sampling interval is typically **~1 second**.
- Missing rates are low on most suites (higher on some RE3 TT cases).
- Some columns are **constant** and should be dropped before ranking (~15 constant metric cols on average for RE2-OB).

### Leakage warning
Folder names **contain the true service and fault**.  
Use them only as labels — never put raw paths into LLM prompts.

### Pre / post split
All analyses should align to `inject_time`:
- **pre-fault** window = baseline / normal behavior  
- **post-fault** window = anomaly evidence  
A later window sweep on RE2-OB preferred **120 seconds** post-inject for our simple ranking features.

---

## 5. Cleaning rules adopted

1. Drop constant / near-constant metric columns.  
2. Align to `inject_time`; use pre-window as baseline.  
3. Never feed case folder names into prompts (label leakage).  
4. Map metrics → services via suffixes.  
5. Treat `redis_*` as `redis-cart` for OB graph alignment.  
6. Expect metrics-only on RE1.  
7. Choose post-fault window carefully (RE2-OB reference: 120s).

---

## 6. How this EDA is used next

EDA does **not** train the final incident-response copilot.  
It prepares honest evaluation on RCAEval:

- score existing baselines (BARO, N-Sigma, E-Diagnosis) with **AC@1 / AC@3 / Avg@5**
- train only a small optional GBT ranker on handmade features
- reset workbook accuracy targets using baseline evidence (see metrics-validation artifacts on the sprint branch)

**Primary reference suite for metric validation:** `re2ob` (90 cases).

---

## 7. How to reproduce

```bash
# from repository root
uv sync --dev

# optional: point at your RCAEval download
export RCAEVAL_DIR="/path/to/RCAEval"

uv run jupyter notebook EDA/RCAEval_EDA.ipynb
```

Notebook outputs also write CSV summaries under `EDA/artifacts/` when executed end-to-end.

---

## 8. Deliverables in this PR

| Path | Description |
|------|-------------|
| `EDA/RCAEval_EDA.ipynb` | Full RCAEval EDA notebook |
| `EDA/RCAEval_EDA_SUMMARY.md` | This summary |
| `EDA/artifacts/` | CSV outputs produced by running the notebook |
