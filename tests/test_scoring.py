import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1]))

from eval.rcaeval.scoring import case_hits, paired_bootstrap, score


def test_case_hits_matches_rcaeval_definitions():
    assert case_hits(["a", "b", "c"], "a") == {"AC@1": 1.0, "AC@3": 1.0, "AC@5": 1.0, "Avg@5": 1.0}
    assert case_hits(["a", "a", "b"], "b")["AC@1"] == 0.0
    assert case_hits(["a", "a", "b"], "b")["Avg@5"] == pytest.approx(0.8)
    assert case_hits([], "x")["Avg@5"] == 0.0


def test_score_reports_overall_and_per_fault_with_cis():
    truth = {"svc1_cpu_1": "svc1", "svc2_cpu_1": "svc2", "svc1_mem_1": "svc1"}
    preds = {"svc1_cpu_1": ["svc1"], "svc2_cpu_1": ["svc1", "svc2"]}
    table = score(preds, truth, n_boot=200)
    assert table.loc["all", "n"] == 3
    assert table.loc["all", "AC@1"] == pytest.approx(1 / 3)
    assert table.loc["cpu", "AC@3"] == 1.0
    assert table.loc["mem", "AC@5"] == 0.0
    assert table.loc["all", "AC@1_lo"] <= table.loc["all", "AC@1"] <= table.loc["all", "AC@1_hi"]


def test_paired_bootstrap_detects_consistent_gain():
    diff, (lo, hi) = paired_bootstrap([1, 1, 1, 1, 0] * 10, [0, 0, 1, 0, 0] * 10, n_boot=500)
    assert diff == pytest.approx(0.6)
    assert 0 < lo <= diff <= hi
    with pytest.raises(ValueError):
        paired_bootstrap([1, 0], [1])
