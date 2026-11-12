"""Scenario registry + ground-truth parsing (E11)."""

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]


def test_registry_lists_pod_crash_and_cpu_stress():
    data = yaml.safe_load((REPO / "scenarios" / "registry.yaml").read_text())
    scenarios = data["scenarios"]
    assert "pod-crash" in scenarios
    assert "cpu-stress" in scenarios
    for sid, spec in scenarios.items():
        inject = REPO / spec["inject"]
        gt = REPO / spec["ground_truth"]
        assert inject.is_file(), sid
        assert gt.is_file(), sid
        ground = yaml.safe_load(gt.read_text())
        assert ground["root_cause_service"]
        assert ground["fault_type"]
