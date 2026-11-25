"""Build the server-free demo site (replay mode) into dist/site.

Every server response in replay mode is deterministic per case, so this drives the
real FastAPI app once per case and stores what the browser needs: the opened
incident, the recorded agent steps, the diagnosis, and the full planner chain
(top-1 plan, then one re-plan per ruled-out service, then escalation).
console/web/static-api.js replays the session state machine from that data.

    uv run python scripts/build_static_site.py
"""

from __future__ import annotations

import json
import shutil
import time

from common.schema import ApprovalDecision
from executor import AllowlistedExecutor
from fastapi.testclient import TestClient

from console import real_incident as ri
from console import web_app

OUT = ri.REPO_ROOT / "dist" / "site"


def _wait_for_diagnosis(client: TestClient, sid: str) -> dict:
    for _ in range(600):
        view = client.get(f"/api/sessions/{sid}").json()
        if view["agent"]["status"] != "running":
            return view
        time.sleep(0.05)
    raise TimeoutError(sid)


def _execution(session: web_app.Session, plan: dict, approved: bool) -> dict:
    model = next(p for p in session.plans if p.id == plan["id"])
    result = AllowlistedExecutor(dry_run=True).execute(
        model, approval_id="approval" if approved else None, approved=approved
    )
    return result.model_dump(mode="json", exclude={"id", "approval_id", "executed_at"})


def build_case(client: TestClient, index: int, case: str) -> dict:
    web_app.SESSIONS.clear()
    opened = client.post(f"/api/incidents/{index}/open").json()
    sid = opened["id"]
    client.post(f"/api/sessions/{sid}/investigate", json={"mode": "saved"})
    view = _wait_for_diagnosis(client, sid)
    session = web_app.SESSIONS[sid]
    agent, diagnosis = view["agent"], view["diagnosis"]
    diagnosis_log = next(e["text"] for e in view["audit"] if e["kind"] == "diagnosis")

    chain = []
    for _ in range(len(diagnosis["candidates"]) + 2):
        if not view["plans"]:
            break
        plan = {k: v for k, v in view["plans"][-1].items() if k != "decision"}
        why = [e["text"] for e in view["audit"] if e["kind"] == "plan"][-1]
        chain.append(
            {
                "plan": plan,
                "log": why,
                "approve": _execution(session, plan, True),
                "reject": _execution(session, plan, False),
            }
        )
        if plan["action"] == "escalate_manual":
            break
        session.gate.decide(plan["id"], decision=ApprovalDecision.REJECT, operator="build")
        session.status = "rejected"
        view = client.post(f"/api/sessions/{sid}/replan", json={}).json()

    revealed = client.post(f"/api/sessions/{sid}/reveal").json()["revealed"]
    return {
        "index": index,
        "label": opened["label"],
        "case_id": opened["case_id"],
        "now": opened["now"],
        "clock_source": opened["clock_source"],
        "opened": {k: opened[k] for k in ("alert", "logs", "overview", "topology", "series")},
        "open_audit": [[e["actor"], e["kind"], e["text"]] for e in opened["audit"]],
        "model": f"{ri.SAVED_RUN} (recorded)",
        "steps": agent["steps"],
        "evidence": agent["evidence"],
        "diagnosis": diagnosis,
        "diagnosis_log": diagnosis_log,
        "chain": chain,
        "truth_service": ri.truth(case)[0],
        "revealed": revealed,
    }


def main() -> None:
    web_app.SAVED_STEP_DELAY = 0
    client = TestClient(web_app.app)
    cases = ri.demo_cases()
    if not cases:
        raise SystemExit(f"No RE2-OB cases under {ri.CASE_ROOT}; run scripts/fetch_re2ob.py")

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "data").mkdir(parents=True)
    shutil.copytree(web_app.WEB, OUT / "static")
    shutil.copytree(web_app.FIGURES, OUT / "figures")
    html = (web_app.WEB / "index.html").read_text()
    html = html.replace(
        '<script src="static/app.js">',
        '<script src="static/static-api.js"></script>\n  <script src="static/app.js">',
    )
    (OUT / "index.html").write_text(html)

    for index, case in enumerate(cases):
        data = build_case(client, index, case)
        (OUT / "data" / f"case_{index}.json").write_text(json.dumps(data, separators=(",", ":")))
        print(f"{data['label']}  {case:32s} {len(data['steps'])} steps, {len(data['chain'])} plans")

    labels = [f"INC-{2401 + i}" for i in range(len(cases))]
    (OUT / "data" / "index.json").write_text(json.dumps({"labels": labels}))
    (OUT / "data" / "evaluation.json").write_text(
        json.dumps(client.get("/api/evaluation").json(), separators=(",", ":"))
    )
    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(f"Wrote {OUT} ({size / 1e6:.1f} MB)")


if __name__ == "__main__":
    main()
