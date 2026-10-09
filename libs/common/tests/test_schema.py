"""Schema validation tests (supports E2 acceptance test: collectors must pass
schema validation)."""

from datetime import UTC, datetime

import pytest
from common.schema import Event, Severity, SignalType
from pydantic import ValidationError


def _valid_kwargs() -> dict:
    return {
        "time": datetime.now(UTC),
        "service": "checkoutservice",
        "pod": "checkoutservice-7d9c-abcde",
        "namespace": "online-boutique",
        "type": SignalType.METRIC,
        "severity": Severity.WARNING,
        "raw_ref": "prom://series/12345",
    }


def test_event_accepts_valid_signal():
    event = Event(**_valid_kwargs())
    assert event.service == "checkoutservice"
    assert event.type is SignalType.METRIC


def test_event_requires_raw_ref_for_evidence():
    kwargs = _valid_kwargs()
    del kwargs["raw_ref"]
    with pytest.raises(ValidationError):
        Event(**kwargs)


def test_event_is_immutable():
    event = Event(**_valid_kwargs())
    with pytest.raises(ValidationError):
        event.service = "mutated"  # type: ignore[misc]
