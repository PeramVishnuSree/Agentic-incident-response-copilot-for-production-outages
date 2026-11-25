RE2-OB, 90 cases, service level. Mean [95% bootstrap CI].

| Method | Source | AC@1 | AC@3 | AC@5 | Avg@5 |
|---|---|---|---|---|---|
| N-Sigma | RCAEval main.py | 0.79 [0.70, 0.87] | 0.94 [0.89, 0.99] | 0.99 [0.97, 1.00] | 0.91 [0.86, 0.95] |
| CIRCA | RCAEval main.py | 0.61 [0.51, 0.71] | 0.89 [0.82, 0.94] | 0.92 [0.87, 0.97] | 0.83 [0.77, 0.89] |
| Multi-source BARO | RCAEval main.py | 0.17 [0.10, 0.24] | 0.88 [0.80, 0.94] | 0.97 [0.92, 1.00] | 0.76 [0.71, 0.80] |
| BARO | RCAEval main.py | 0.14 [0.08, 0.22] | 0.88 [0.80, 0.94] | 0.94 [0.89, 0.99] | 0.74 [0.69, 0.79] |
| RCD | RCAEval main.py (Py 3.8 env) | 0.68 [0.57, 0.77] | 0.73 [0.64, 0.82] | 0.81 [0.72, 0.89] | 0.75 [0.66, 0.83] |
| PDiagnose | port of upstream demo | 0.38 [0.29, 0.48] | 0.91 [0.84, 0.97] | 0.99 [0.97, 1.00] | 0.80 [0.75, 0.84] |
| E-Diagnosis | RCAEval main.py | 0.03 [0.00, 0.08] | 0.18 [0.10, 0.26] | 0.18 [0.10, 0.26] | 0.14 [0.08, 0.20] |
| Random ranking | RCAEval main.py | 0.12 [0.06, 0.19] | 0.30 [0.21, 0.40] | 0.51 [0.41, 0.61] | 0.31 [0.23, 0.38] |
| BARO, our original harness (the 0.30) | diagnostic | 0.30 [0.21, 0.40] | 0.92 [0.87, 0.97] | 1.00 [1.00, 1.00] | 0.80 [0.77, 0.84] |
| BARO + zero-IQR guard | diagnostic, not a baseline | 0.81 [0.73, 0.89] | 0.91 [0.84, 0.97] | 0.94 [0.89, 0.99] | 0.90 [0.84, 0.95] |

Avg@5 per fault type:

| Method | CPU | MEM | DISK | SOCKET | DELAY | LOSS |
|---|---|---|---|---|---|---|
| N-Sigma | 0.83 | 0.99 | 0.99 | 0.87 | 0.89 | 0.91 |
| CIRCA | 0.77 | 0.93 | 0.87 | 0.83 | 0.75 | 0.84 |
| Multi-source BARO | 0.65 | 0.89 | 0.80 | 0.71 | 0.67 | 0.81 |
| BARO | 0.64 | 0.87 | 0.81 | 0.67 | 0.67 | 0.80 |
| RCD | 1.00 | 0.67 | 0.89 | 0.87 | 0.81 | 0.24 |
| PDiagnose | 0.85 | 0.84 | 0.87 | 0.79 | 0.75 | 0.69 |
| E-Diagnosis | 0.04 | 0.15 | 0.07 | 0.20 | 0.23 | 0.15 |
| Random ranking | 0.41 | 0.27 | 0.35 | 0.43 | 0.17 | 0.21 |
| BARO, our original harness (the 0.30) | 0.77 | 0.89 | 0.96 | 0.76 | 0.69 | 0.75 |
| BARO + zero-IQR guard | 0.80 | 1.00 | 0.99 | 0.84 | 0.84 | 0.91 |

Same 30 cases (one per service x fault), LLM agent = mlx-community/Qwen3-4B-4bit prompt v2:

| Method | AC@1 | AC@3 | Avg@5 |
|---|---|---|---|
| LLM agent (N3) | 0.93 [0.83, 1.00] | 1.00 [1.00, 1.00] | 0.98 [0.95, 1.00] |
| N-Sigma | 0.83 [0.67, 0.97] | 0.97 [0.90, 1.00] | 0.93 [0.86, 0.99] |
| CIRCA | 0.57 [0.40, 0.73] | 0.90 [0.80, 1.00] | 0.83 [0.71, 0.92] |
| PDiagnose | 0.43 [0.27, 0.63] | 0.90 [0.77, 1.00] | 0.81 [0.74, 0.88] |
| RCD | 0.70 [0.53, 0.87] | 0.77 [0.60, 0.90] | 0.77 [0.63, 0.90] |
| BARO | 0.13 [0.03, 0.27] | 0.87 [0.73, 0.97] | 0.76 [0.68, 0.83] |
| Multi-source BARO | 0.13 [0.03, 0.27] | 0.87 [0.73, 0.97] | 0.74 [0.65, 0.81] |

Paired bootstrap, agent minus baseline (95% CI):

- agent_minus_nsigma_AC@1: +0.10 [-0.07, +0.27]
- agent_minus_nsigma_Avg@5: +0.05 [-0.02, +0.13]
- agent_minus_circa_AC@1: +0.37 [+0.13, +0.57]
- agent_minus_circa_Avg@5: +0.15 [+0.05, +0.27]
- agent_minus_pdiagnose_AC@1: +0.50 [+0.33, +0.67]
- agent_minus_pdiagnose_Avg@5: +0.17 [+0.11, +0.23]
- agent_minus_rcd_AC@1: +0.23 [+0.10, +0.40]
- agent_minus_rcd_Avg@5: +0.21 [+0.08, +0.35]
- agent_minus_baro_AC@1: +0.80 [+0.60, +0.93]
- agent_minus_baro_Avg@5: +0.22 [+0.14, +0.31]
- agent_minus_mmbaro_AC@1: +0.80 [+0.60, +0.93]
- agent_minus_mmbaro_Avg@5: +0.24 [+0.15, +0.34]
