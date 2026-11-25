# N1 baseline reproduction: RE2-OB

The write-up, the single table with 95% CIs, the redis/0.30 explanation and the
provenance are in [`docs/baselines.md`](../../../docs/baselines.md).

Artifacts in this directory:

- `official_runs/<method>/`: stdout, stderr, per-case rankings (`results/*.json`)
  and `run.json` (command, commit, Python) for every RCAEval `main.py` run
  (baro, mmbaro, nsigma, e_diagnosis, circa, rcd, dummy) and the PDiagnose port;
  `official_runs/provenance.json` aggregates them.
- `n1/n1_results.json`, `n1/n1_table.md`: scored by `eval/rcaeval/scoring.py`
  (AC@1/3/5, Avg@5, CIs, per fault; the agent comparison on the same cases).
- `n1/redis_hypothesis.json`: preprocessing variants A0–F.

Earlier entries in this file are withdrawn. "Project BARO 0.744" came from raw
`metrics.csv` input with non-unique case ids. "RCD incompatible" came from
skipping upstream's `script/link.sh`. "CIRCA not registered" was an environment
issue. The PDiagnose adapter numbers came from a non-faithful adapter.
