# Metrics validation (Workbook professor item #3)

**Question:** Have any preliminary experiments validated the evaluation metrics?
**Answer now:** Yes — RE2-OB pilot with BARO + other RCAEval metric baselines,
bootstrap 95% CIs, revised targets relative to BARO (per fault), and a study-size calc.

Suite: `re2ob` · cases: **90** · date: 2026-11-09

## 1. Baselines on RE2-OB (empirical reference)

| Method | AC@1 (95% CI) | AC@3 (95% CI) | Avg@5 (95% CI) |
|--------|--------------:|--------------:|---------------:|
| baro | 0.300 [0.211, 0.389] | 0.922 [0.867, 0.978] | 0.804 [0.764, 0.840] |
| nsigma | 0.856 [0.778, 0.922] | 0.967 [0.922, 1.000] | 0.951 [0.920, 0.978] |
| e_diagnosis | 0.111 [0.056, 0.178] | 0.189 [0.111, 0.278] | 0.173 [0.102, 0.249] |
| gbt_ranker | 0.889 [0.822, 0.944] | 0.978 [0.944, 1.000] | 0.962 [0.929, 0.987] |

Published context: BARO paper/repo reports Avg@5 ≈ 0.86 on Online Boutique metric data;
our RE2-OB BARO Avg@5 = **0.804** (95% CI [0.764, 0.840]).

### BARO per fault (95% bootstrap CI)

| Fault | AC@1 | AC@3 | Avg@5 |
|-------|-----:|-----:|------:|
| cpu | 0.067 [0.000, 0.200] | 1.000 [1.000, 1.000] | 0.773 [0.720, 0.827] |
| delay | 0.067 [0.000, 0.200] | 0.800 [0.600, 1.000] | 0.693 [0.573, 0.800] |
| disk | 0.867 [0.667, 1.000] | 1.000 [1.000, 1.000] | 0.960 [0.893, 1.000] |
| loss | 0.267 [0.067, 0.467] | 0.800 [0.600, 1.000] | 0.747 [0.613, 0.853] |
| mem | 0.467 [0.200, 0.733] | 1.000 [1.000, 1.000] | 0.893 [0.840, 0.947] |
| socket | 0.067 [0.000, 0.200] | 0.933 [0.800, 1.000] | 0.760 [0.693, 0.827] |

## 2. Revised targets (replace workbook 60% / 85%)

- Old (unvalidated): AC@1 ≥ 0.6, AC@3 ≥ 0.85
- Clear BARO 95% CI: AC@1 ≥ **0.439**
- **Engineering gate** (beat BARO + competitive with N-Sigma): AC@1 ≥ **0.778**, AC@3 ≥ **0.922**, Avg@5 ≥ **0.86**
- **Stretch:** AC@1 ≥ **0.856**, AC@3 ≥ **0.95**
- BARO reference AC@1 = 0.3 (95% CI [0.211, 0.389]); N-Sigma AC@1 = 0.856

| Fault | BARO AC@1 | Target AC@1 | BARO AC@3 | Target AC@3 |
|-------|----------:|------------:|----------:|------------:|
| cpu | 0.067 | **0.500** | 1.000 | **1.000** |
| delay | 0.067 | **0.500** | 0.800 | **0.850** |
| disk | 0.867 | **0.867** | 1.000 | **1.000** |
| loss | 0.267 | **0.567** | 0.800 | **0.850** |
| mem | 0.467 | **0.833** | 1.000 | **1.000** |
| socket | 0.067 | **0.500** | 0.933 | **0.933** |

## 3. Human-study sizing from pilot variance

- Pilot BARO AC@1 = 0.3, ranker AC@1 = 0.889
- To detect +15pp over BARO (80% power, α=0.05): **n ≈ 151 labelled cases / arm**
- To estimate our AC@1 within ±5pp: **n ≈ 152**
- Per-fault stratum (±15pp, worst-case p=0.5): **n ≈ 43 / fault** × 6 faults
- Recommended labelled eval budget: **≥ 152 cases**
- Human TTRC pilot: **~12 operators** (within-subject) to estimate SD, then re-size Semester B

## 4. What this closes

- Metrics AC@k / Avg@5 are empirically grounded on public RCAEval RE2-OB.
- Targets are relative to BARO (overall + per fault), with bootstrap CIs.
- Pilot variance sizes the accuracy arm of the human study; TTRC still needs a timed pilot.

## Reproduce

```bash
uv run python -m eval.rcaeval.metrics_validation --suite re2ob
```

Artifacts: `re2ob_*_cases.json`, `re2ob_metrics_validation.json`, this file.
