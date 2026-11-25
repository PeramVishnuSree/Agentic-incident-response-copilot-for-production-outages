"""End-to-end early prototype: signals → diagnose → plan → approve → dry-run execute."""

from console.cli.prototype import run_prototype


def test_vertical_prototype_cpu_stress_ac_at_1():
    result = run_prototype("cpu-stress", operator="pytest", approve=True)
    assert result["ground_truth"]["service"] == "cartservice"
    assert result["ac_at_1"] is True
    assert result["plan"]["target_service"] == "cartservice"
    assert result["approval"]["decision"] == "approve"
    assert result["execution"]["status"] == "dry_run"
    assert result["execution"]["dry_run"] is True


def test_vertical_prototype_pod_crash():
    result = run_prototype("pod-crash", operator="pytest", approve=True)
    assert result["ground_truth"]["service"] == "checkoutservice"
    assert result["ac_at_3"] is True
    assert result["plan"]["action"] in {
        "restart_pod",
        "rollout_restart",
        "rollout-restart",
        "escalate_manual",
    }


def test_reject_blocks_execute():
    result = run_prototype("cpu-stress", approve=False)
    assert result["execution"]["status"] == "rejected"


def test_feedback_loop_second_attempt():
    result = run_prototype("cpu-stress", approve=True, simulate_failure_loop=True)
    assert result["feedback_loop"] is not None
    assert result["feedback_loop"]["second_plan"]["id"] != result["plan"]["id"]
