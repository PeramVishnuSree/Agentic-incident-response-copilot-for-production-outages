import time

import pytest
from fastapi.testclient import TestClient

from console import real_incident as ri
from console import web_app

pytestmark = pytest.mark.skipif(
    not ri.demo_cases() or ri.saved_trajectory(ri.demo_cases()[0]) is None,
    reason="RE2-OB replay data or saved trajectories not available",
)


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(web_app, "SAVED_STEP_DELAY", 0)
    web_app.SESSIONS.clear()
    return TestClient(web_app.app)


def _diagnose(client, index):
    view = client.post(f"/api/incidents/{index}/open").json()
    client.post(f"/api/sessions/{view['id']}/investigate", json={"mode": "saved"})
    for _ in range(100):
        view = client.get(f"/api/sessions/{view['id']}").json()
        if view["agent"]["status"] != "running":
            return view
        time.sleep(0.05)
    raise AssertionError("investigation did not finish")


def _decide(client, sid, decision="approve"):
    body = {"decision": decision, "operator": "tester", "note": "test"}
    return client.post(f"/api/sessions/{sid}/decision", json=body).json()


def test_page_and_incident_view_do_not_leak_the_answer(client):
    assert "Incident Copilot" in client.get("/").text
    view = client.post("/api/incidents/0/open").json()
    service, _ = ri.truth(ri.demo_cases()[0])
    case = ri.demo_cases()[0]
    blob = str({k: v for k, v in view.items() if k not in {"topology", "overview", "series"}})
    assert case not in blob and "re2ob" not in blob
    assert view["case_id"].startswith("replay-")
    assert view["status"] == "detected"
    assert view["series"] and view["alert"]["symptoms"]
    assert service in view["topology"]["services"]


def test_full_flow_resolves_when_top1_is_right(client):
    view = _diagnose(client, 0)
    assert view["status"] == "awaiting_approval"
    assert view["diagnosis"]["top_services"][0] == ri.truth(ri.demo_cases()[0])[0]
    assert view["agent"]["evidence"]
    view = _decide(client, view["id"])
    assert view["status"] == "verifying"
    assert view["attempts"][0]["execution"]["status"] == "dry_run"
    view = client.post(f"/api/sessions/{view['id']}/verify", json={"outcome": "simulate"}).json()
    assert view["status"] == "resolved"
    view = client.post(f"/api/sessions/{view['id']}/reveal").json()
    assert view["revealed"]["agent_rank"] == 1
    kinds = [e["kind"] for e in view["audit"]]
    assert kinds.index("approval") < kinds.index("execute") < kinds.index("verify")


def test_rejection_and_failed_remedy_loop_to_next_candidate(client):
    view = _diagnose(client, 0)
    first = view["plans"][-1]["target_service"]
    view = _decide(client, view["id"], "reject")
    assert view["status"] == "rejected"
    assert view["attempts"][0]["execution"]["status"] == "rejected"
    view = client.post(f"/api/sessions/{view['id']}/replan", json={}).json()
    assert view["status"] == "awaiting_approval"
    second = view["plans"][-1]["target_service"]
    assert second != first
    view = _decide(client, view["id"])
    view = client.post(
        f"/api/sessions/{view['id']}/verify", json={"outcome": "not_recovered", "operator": "t"}
    ).json()
    assert view["status"] == "awaiting_approval"
    assert view["plans"][-1]["target_service"] not in {first, second}


def test_decision_requires_a_pending_plan(client):
    view = client.post("/api/incidents/1/open").json()
    response = client.post(
        f"/api/sessions/{view['id']}/decision", json={"decision": "approve", "operator": "x"}
    )
    assert response.status_code == 409


def test_evaluation_endpoint(client):
    data = client.get("/api/evaluation").json()
    assert "nsigma" in data["n1"]["methods"]
    assert data["runs"] and "failure" in data["failure_modes"].lower()
