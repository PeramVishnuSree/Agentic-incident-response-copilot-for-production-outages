"""Collector + normalizer tests (E1, E2)."""

from common.schema import SignalType
from fastapi.testclient import TestClient
from telemetry_gateway.collectors.alerts import from_alertmanager_payload
from telemetry_gateway.collectors.k8s_events import from_k8s_event
from telemetry_gateway.collectors.metrics import from_prom_sample
from telemetry_gateway.main import app
from telemetry_gateway.store import STORE

client = TestClient(app)


def setup_function() -> None:
    STORE.clear()


def test_alertmanager_webhook_normalises_and_stores():
    payload = {
        "alerts": [
            {
                "labels": {
                    "alertname": "HighPodRestartRate",
                    "service": "checkoutservice",
                    "severity": "critical",
                    "namespace": "online-boutique",
                    "pod": "checkoutservice-abc",
                },
                "annotations": {"summary": "pod restarting"},
                "startsAt": "2026-11-03T12:01:07Z",
            }
        ]
    }
    events = from_alertmanager_payload(payload)
    assert len(events) == 1
    assert events[0].type is SignalType.ALERT
    assert events[0].service == "checkoutservice"
    assert events[0].raw_ref.startswith("am://")

    resp = client.post("/webhook/alertmanager", json=payload)
    assert resp.status_code == 200
    assert resp.json()["accepted"] == 1
    assert len(client.get("/events").json()) == 1


def test_k8s_event_and_metric_collectors_emit_valid_events():
    ke = from_k8s_event(
        {
            "metadata": {
                "uid": "u1",
                "namespace": "online-boutique",
                "labels": {"app": "cartservice"},
            },
            "involvedObject": {"kind": "Pod", "name": "cartservice-1"},
            "reason": "Killing",
            "type": "Warning",
            "message": "Stopping container",
            "lastTimestamp": "2026-11-03T12:00:00Z",
        }
    )
    assert ke.type is SignalType.K8S_EVENT
    assert ke.service == "cartservice"

    me = from_prom_sample(
        {
            "metric": {"__name__": "container_cpu_usage_seconds_total", "app": "cartservice"},
            "timestamp": "2026-11-03T12:00:10Z",
            "value": 1.5,
        }
    )
    assert me.type is SignalType.METRIC
    assert me.service == "cartservice"
