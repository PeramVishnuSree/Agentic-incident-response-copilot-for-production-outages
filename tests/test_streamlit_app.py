from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from console import real_incident as ri

APP = str(Path(__file__).resolve().parents[1] / "console" / "streamlit_app.py")


def _button(at: AppTest, label: str):
    return next(b for b in at.button if b.label.startswith(label))


@pytest.mark.skipif(
    not ri.demo_cases() or ri.saved_trajectory(ri.demo_cases()[0]) is None,
    reason="RE2-OB replay data or saved trajectories not available",
)
def test_real_incident_flow_end_to_end():
    at = AppTest.from_file(APP, default_timeout=120).run()
    assert not at.exception
    case_id = at.metric[0].value

    _button(at, "Replay saved trajectory").click().run()
    assert not at.exception
    assert at.metric[0].value == case_id

    _button(at, "Approve plan").click().run()
    assert any("DRY-RUN" in c.value for c in at.code)

    at.toggle(key="ri_run_reveal").set_value(True).run()
    assert not at.exception
    assert any(m.label == "True root cause" for m in at.metric)


def test_scripted_scenario_runs():
    at = AppTest.from_file(APP, default_timeout=120).run()
    _button(at, "Run diagnosis").click().run()
    assert not at.exception
    assert any(m.label == "Top-1 service" for m in at.metric)
