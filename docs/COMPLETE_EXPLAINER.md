# Complete explainer — Project + RCAEval (plain English)

**Course:** CMPE 295 · Agentic Incident-Response Copilot  
**Audience:** teammates / advisor who want the full story without jargon  
**Last updated:** 2026-11-12

This document explains **everything we have done and talked about**: the product architecture, what RCAEval is, apps vs releases, faults, columns, EDA, time windows, BARO, N-Sigma, E-Diagnosis, the small GBT ranker, accuracy scores, old vs new targets, and what is / is not finished.

---

## 1. What our project is trying to do

When a cloud app breaks, many small programs (**services**) talk to each other. Usually **one** service is the real problem (the **root cause**). Finding it is hard and slow for humans.

Our project builds a **helper (copilot)** that:

1. Collects signals (metrics, logs, alerts, …)
2. Groups related signals into an “incident”
3. Ranks which services look most suspicious
4. Explains the guess with evidence
5. Asks a **human** before any fix
6. Only then runs a **restricted** fix path

We did **not** invent our evaluation dataset. We use a public benchmark called **RCAEval** as a practice exam with known answers.

---

## 2. Product architecture (how the system is designed)

High-level flow:

```
 target cluster ─▶ telemetry-gateway ─▶ incident store
 (Online Boutique)   (collectors +           │
  + Chaos Mesh)        normaliser)           ▼
                                       correlation-engine
                                       (group signals + rank top services)
                                                 │
                                                 ▼
                                             rca-agent
                                       (read-only tools + evidence)
                                                 │
                                                 ▼
                                        remediation-planner
                                       (draft fix plan + undo notes)
                                                 │
                                                 ▼
                                          human approval
                                                 │
                                                 ▼
                                        restricted-executor
                                       (ONLY component that can write)
```

### Important safety idea

- **Diagnosis path is read-only** (look and explain).
- **Only the restricted executor** can change the cluster.
- A human must approve before writes.

### Repo pieces (where code lives)

| Area | Role |
|------|------|
| `services/telemetry-gateway/` | Collect / normalize telemetry |
| `services/correlation-engine/` | Group signals + dependency-graph ranking |
| `services/rca-agent/` | Read-only investigation tools |
| `config/dependency-graph.yaml` | Service dependency graph (Online Boutique) |
| `scenarios/` | Chaos Mesh fault scenarios (pod-crash, cpu-stress) |
| `eval/rcaeval/` | RCAEval experiment harness (EDA, baselines, ranker) |
| `EDA/` | Course EDA notebook + summary |
| `docs/` | Architecture, baselines, progress, this explainer |

More detail: [`architecture.md`](architecture.md).

---

## 3. What RCAEval is

**RCAEval** = a public **benchmark dataset** made by other researchers.

It contains hundreds of **fake but realistic incidents**. For each incident they already know:

- which **service** was broken
- what **fault type** was injected

So we can score any method fairly: “Did you rank the true service near the top?”

We **downloaded** RCAEval. We did **not** create it.

Official project: https://github.com/phamquiluan/RCAEval

---

## 4. Apps vs releases (this confused people — simple version)

Think of a **grid**.

### Apps = which demo system was broken

1. **OB — Online Boutique**  
   Google’s small demo online shop. Fewer services. Easier.

2. **SS — Sock Shop**  
   Another demo shop. Medium size.

3. **TT — Train Ticket**  
   Big train-booking demo. Many services. Harder.

### Releases = which RCAEval data pack / edition

1. **RE1**  
   Mostly **metrics only** (CPU, memory, latency charts). Usually no rich logs/traces.

2. **RE2**  
   Richer: metrics + often **logs** and **traces**. Also adds **socket** faults.

3. **RE3**  
   Harder **code/functional bug** faults labeled `f1`, `f2`, `f3`, … (not only CPU stress).

### Suite = one app + one release

Examples:

- `re2ob` = Release 2 + Online Boutique  
- `re1tt` = Release 1 + Train Ticket  
- `re3ss` = Release 3 + Sock Shop  

**All datasets for us** = 3 apps × 3 releases = **9 suites** = **735 cases** in our local copy.

---

## 5. What a “fault” is

A **fault** is the kind of problem they injected on purpose.

### RE1 / RE2 faults

| Fault | Plain meaning |
|-------|----------------|
| `cpu` | Force high CPU |
| `mem` | Force high memory |
| `disk` | Stress disk I/O |
| `delay` | Slow the network |
| `loss` | Drop packets |
| `socket` | Socket/network fault (mainly RE2) |

### RE3 faults

`f1` … `f5` style functional/code bugs.  
In our download: OB has f1–f5; SS/TT have f1–f4.

---

## 6. What’s inside one RCAEval case

Each case is a folder. Example name:

`re2ob_checkoutservice_cpu_1`

That name already encodes the answer:

- suite = `re2ob`
- true service = `checkoutservice`
- fault = `cpu`
- repeat id = `1`

### Files

| File | Meaning |
|------|---------|
| `metrics.parquet` | Table of numbers over time |
| `logs.parquet` | Log text lines (RE2/RE3 when present) |
| `traces.parquet` | Request trace spans (when present) |
| `inject_time.txt` | Exact time the fault starts |

### What “columns” means

In metrics, each **column** is one sensor over time.

Examples:

- `time` → clock  
- `checkoutservice_cpu` → checkout CPU  
- `cartservice_latency-90` → cart latency (90th percentile)  
- `redis_mem` → Redis memory  

**Rows** = different seconds.  
We map a column → service by stripping suffixes like `_cpu`, `_mem`, `_latency-90`.  
`redis_*` is treated as `redis-cart` for Online Boutique naming.

### Label leakage warning

Because the folder name contains the true answer, we must **never** put raw folder paths into an LLM prompt. Use the name only as the grading label.

---

## 7. How EDA was done

**EDA = Exploratory Data Analysis** = open the boxes and understand the data before modeling.

We:

1. Counted cases / suites / faults / services  
2. Checked which files exist (metrics / logs / traces)  
3. Measured metric width, missing values, constant columns, sampling rate  
4. Separated pre-fault vs post-fault around `inject_time`  
5. Wrote cleaning rules  
6. Saved a notebook + summary for course submission  

### Deliverables

- Notebook: `EDA/RCAEval_EDA.ipynb`  
- Short summary: `EDA/RCAEval_EDA_SUMMARY.md`  
- CSV outputs: `EDA/artifacts/`  
- Scripted deep EDA also under `eval/rcaeval/deep_eda.py` and `eval/artifacts/rcaeval/`

### Inventory snapshot (735 cases)

| Suite | Cases | Avg metric cols | Avg logs | Avg traces |
|-------|------:|----------------:|---------:|-----------:|
| re1ob | 125 | 54 | 0 | 0 |
| re1ss | 125 | 59 | 0 | 0 |
| re1tt | 125 | 214 | 0 | 0 |
| re2ob | 90 | 73 | ~167k | ~383k |
| re2ss | 90 | 77 | ~84k | 0 |
| re2tt | 90 | 362 | ~233k | ~748k |
| re3ob | 30 | 70 | ~70k | ~159k |
| re3ss | 30 | 83 | ~77k | 0 |
| re3tt | 30 | 315 | ~54k | ~138k |

RE1 is metrics-only. Train Ticket has many more metric columns → harder.

### Cleaning rules from EDA

1. Drop constant / near-constant metric columns.  
2. Align everything to `inject_time`; use pre-fault as baseline.  
3. Never put case folder names into prompts.  
4. Map metrics → services via suffixes.  
5. Treat `redis_*` as `redis-cart` for OB.  
6. Do not expect logs/traces on RE1.  
7. Choose post-fault time window carefully.

---

## 8. What a “time window” means

After `inject_time`, we do not always use the whole long recording.

We look at only the next **W seconds**. That **W** is the **time window**.

```
normal period     inject      window we use
-------------------|============|----------> time
                   ^            ^
              fault starts   stop looking
```

- Too short → signal may not appear yet  
- Too long → side effects / noise bury the real culprit  

On **RE2-OB** we tried 30, 60, 120, 300, 600, 900 seconds.  
**120 seconds** looked best for our simple ranking features.

---

## 9. Accuracy metrics (AC@1 / top-1, etc.)

Every method outputs a **ranked list of services**, like:

1. cartservice  
2. checkoutservice  
3. frontend  

If the true answer is `checkoutservice`:

- **AC@1 / top-1** = is #1 correct? → here **no**  
- **AC@3 / top-3** = is truth in top 3? → here **yes**  
- **Avg@5** = average hit rate across top-1…top-5  

Average these 0/1 scores over all cases → the reported accuracy.

**Where used:** grading BARO, N-Sigma, E-Diagnosis, our GBT ranker, and setting project targets.

---

## 10. Existing baselines we ran (we did not invent these)

These are **finished methods from RCAEval / papers**. We pressed run and scored them.

### BARO

Published metric RCA method.

Simple idea:

1. Watch metric charts  
2. Find big changes after the fault starts  
3. Rank suspicious services  

On **RE2-OB (90 cases)** our run:

| Score | Value |
|------:|------:|
| AC@1 | ~0.30 |
| AC@3 | ~0.92 |
| Avg@5 | ~0.80 |

Published BARO reference on Online Boutique metric data is about **Avg@5 ≈ 0.86**. Our RE2-OB number is nearby.

BARO is often weak at exact #1, stronger at getting truth into top-3.

Per-fault on RE2-OB (BARO AC@1 roughly):

- disk high (~0.87)  
- mem medium (~0.47)  
- loss lower (~0.27)  
- cpu / delay / socket very low (~0.07)

So some faults are much harder than others. That is why we set **per-fault targets**, not one fake number for everything.

### N-Sigma

Simple “this number is many standard deviations from normal” detector, then rank services.

On same RE2-OB cases:

| Score | Value |
|------:|------:|
| AC@1 | ~0.86 |
| AC@3 | ~0.97 |

So on this suite, N-Sigma beats BARO at top-1. Useful competitor.

### E-Diagnosis

Another RCAEval baseline. On RE2-OB it was weak (~0.11 AC@1). Kept as a lower reference.

---

## 11. What the GBT ranker is (the only model we trained)

**GBT** = Gradient Boosting classifier (small classical ML model in scikit-learn).

This is **not** ChatGPT, **not** a deep custom neural net, **not** the full copilot brain.

### What it does

1. For each case and each service, compute a few handmade features:
   - anomaly score (how weird metrics look after the fault)
   - onset time (how soon weirdness starts)
   - log error-ish rate (when logs exist)
   - upstreamness in the dependency graph
   - number of metrics for that service
2. Train to predict: “is this service the root cause?” (yes/no)
3. Sort services by predicted score → ranking
4. Grade with AC@1 / AC@3

On RE2-OB: about **AC@1 ≈ 0.89**, **AC@3 ≈ 0.98** (cross-validated by case).

Treat it as a **pilot ranking model**, proof that learned ranking can work on these features — not the finished product AI.

### BARO vs GBT one-liner

- **BARO / N-Sigma / E-Diagnosis:** existing algorithms → we ran them.  
- **GBT:** we built features + trained a small ranker ourselves.

---

## 12. What we ran on all datasets

We ran the harness across **all 9 suites (735 cases)**:

- deep EDA  
- window sweep  
- GBT ranker  
- BARO  

Master table: `eval/artifacts/rcaeval/ALL_SUITES_RESULTS.md`

Example highlights:

| Suite | Ranker AC@1 | BARO AC@1 |
|-------|------------:|----------:|
| re2ob | 0.889 | 0.300 |
| re2ss | 0.922 | 0.111 |
| re2tt | 0.633 | 0.422 |
| re1tt | 0.560 | 0.120 |

Harder systems (especially Train Ticket) score lower. Expected.

Deeper metrics-validation write-up (bootstrap CIs, revised targets, study size) is centered on **RE2-OB**, the main Online Boutique reference the review asked for:

`eval/artifacts/rcaeval/METRICS_VALIDATION.md`

---

## 13. Required vs current targets

### Old workbook targets (not validated)

- top-1 ≥ **60%**  
- top-3 ≥ **85%**  

These were **guesses**, not derived from experiments. Professor feedback: validate metrics with baselines.

### What we measured (RE2-OB)

| Method | Top-1 | Top-3 |
|--------|------:|------:|
| BARO | ~30% | ~92% |
| N-Sigma | ~86% | ~97% |
| Our GBT | ~89% | ~98% |

### New engineering targets (from baselines)

Roughly:

- Gate: AC@1 ≥ **~0.78**, AC@3 ≥ **~0.92**, Avg@5 ≥ **~0.86**  
- Stretch: AC@1 ≥ **~0.86**, AC@3 ≥ **~0.95**  
- Plus **per-fault gates** (disk already high for BARO; cpu/delay/socket harder)

Human-study sizing from that pilot variance: about **≥152 labelled cases** for accuracy estimation; ~**12 operators** for a first time-to-RCA variance pilot.

---

## 14. Full checklist — what we have done

1. Chose public RCAEval (not a hand-made private dataset).  
2. Downloaded all 9 suites (735 cases).  
3. Built eval helpers under `eval/rcaeval/`.  
4. Did EDA (script + notebook + summary).  
5. Chose time windows (RE2-OB preferred 120s).  
6. Ran BARO on all suites; N-Sigma + E-Diagnosis on RE2-OB.  
7. Trained/evaluated a small GBT ranker.  
8. Wrote all-suite results + metrics validation with bootstrap CIs.  
9. Replaced arbitrary 60%/85% with baseline-relative targets.  
10. Sized the accuracy arm of the human study from pilot variance.  
11. Put deliverables in git on one PR branch (`feature/sprint2-diagnosis-eda`).

---

## 15. What we have NOT finished yet

- Full **LLM agentic copilot** evaluated end-to-end on all 735 RCAEval cases  
- Live-cluster baselines like **HolmesGPT** (needs kind cluster up)  
- Same depth of N-Sigma + CI rewrite on every suite (deep validation focused on RE2-OB)  
- Human timed study actually run (only sized so far)  
- PostgreSQL store / approval UI / restricted executor productization (next sprints)

---

## 16. How to reproduce

```bash
# from repo root
uv sync --dev
uv run pytest

# point at RCAEval download
export RCAEVAL_DIR="/path/to/RCAEval"   # or use ../datasets/RCAEval

# course EDA notebook
uv run jupyter notebook EDA/RCAEval_EDA.ipynb

# full suite track
make rcaeval-everything

# metrics validation (baselines + CIs + revised targets)
make rcaeval-metrics-validation
```

---

## 17. One-paragraph summary 

We use the public RCAEval benchmark (9 suites, 735 labelled cases across Online Boutique, Sock Shop, and Train Ticket) as our evaluation corpus. We completed exploratory data analysis, documented columns/leakage/cleaning rules, selected a post-fault analysis window, and ran existing metric baselines (BARO, N-Sigma, E-Diagnosis) plus a small gradient-boosting service ranker. Scores use AC@1 / AC@3 / Avg@5 with bootstrap confidence intervals on RE2-OB. The old workbook 60%/85% targets were replaced with baseline-relative, per-fault gates. The product architecture separates read-only diagnosis from a human-approved restricted executor; the full LLM copilot path is designed but not yet fully evaluated on every RCAEval case.

---

## 18. Related files

| File | Content |
|------|---------|
| [`architecture.md`](architecture.md) | System diagram + safety boundary |
| [`baselines.md`](baselines.md) | BARO / N-Sigma / HolmesGPT notes |
| [`PROGRESS.md`](PROGRESS.md) | Status checklist |
| [`../EDA/RCAEval_EDA.ipynb`](../EDA/RCAEval_EDA.ipynb) | EDA notebook |
| [`../EDA/RCAEval_EDA_SUMMARY.md`](../EDA/RCAEval_EDA_SUMMARY.md) | Short EDA summary |
| [`../eval/artifacts/rcaeval/ALL_SUITES_RESULTS.md`](../eval/artifacts/rcaeval/ALL_SUITES_RESULTS.md) | All-suite score table |
| [`../eval/artifacts/rcaeval/METRICS_VALIDATION.md`](../eval/artifacts/rcaeval/METRICS_VALIDATION.md) | Targets + CIs + study size |
