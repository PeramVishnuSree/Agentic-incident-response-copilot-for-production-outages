import json

import pytest
from remediation_planner import draft_plan

from console import real_incident as ri

TRAJECTORY = {
    "top_services": ["emailservice", "checkoutservice"],
    "claims": [{"service": "emailservice", "claim": "memory leak", "evidence_refs": ["E1"]}],
    "messages": [
        {
            "role": "tool",
            "name": "get_metrics",
            "content": json.dumps(
                {
                    "metrics": [
                        {"metric": "emailservice_latency-90", "z_score": 120.0},
                        {"metric": "emailservice_mem", "z_score": -4000.0},
                        {"metric": "frontend_cpu", "z_score": 9000.0},
                    ]
                }
            ),
        }
    ],
}


def test_fault_hint_uses_strongest_metric_of_top_service():
    assert ri.fault_hint(TRAJECTORY, "emailservice") == ("mem", "emailservice_mem")


def test_resource_first_prefers_resource_change_over_larger_latency():
    rows = [
        {"metric": "cartservice_latency-90", "z_score": 300.0},
        {"metric": "cartservice_cpu", "z_score": 5.0},
        {"metric": "cartservice_mem", "z_score": 2.0},
    ]
    assert ri.classify_fault(rows, "cartservice", "max") == ("delay", "cartservice_latency-90")
    assert ri.classify_fault(rows, "cartservice") == ("cpu", "cartservice_cpu")
    weak = [r for r in rows if not r["metric"].endswith("cpu")]
    assert ri.classify_fault(weak, "cartservice") == ("delay", "cartservice_latency-90")
    assert ri.fault_hint(TRAJECTORY, "adservice") == ("unknown", None)


def test_agent_ranking_feeds_the_playbook_planner():
    cands = ri.candidates(TRAJECTORY)
    assert [c.service for c in cands] == ["emailservice", "checkoutservice"]
    assert cands[0].evidence == ["E1"]
    plan = draft_plan(incident_id="replay-x", candidates=cands, fault_type="mem")
    assert plan.target_service == "emailservice"
    assert plan.playbook_id == "PB-03"


@pytest.mark.skipif(not ri.demo_cases(), reason="RE2-OB replay data not available")
def test_demo_cases_are_one_per_service_and_fault():
    cases = ri.demo_cases()
    assert len(cases) == 30
    assert len({ri.truth(c) for c in cases}) == 30
