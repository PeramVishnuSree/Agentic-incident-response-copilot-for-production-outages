"""CMPE 295A early prototype — Streamlit operator console.

Run:
  cd repo && uv run streamlit run console/streamlit_app.py
Optional, for live agent runs:
  mlx_lm.server --model mlx-community/Qwen3-4B-4bit --port 8080
"""

from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pandas as pd  # noqa: E402
import streamlit as st  # noqa: E402
from approval_service import ApprovalGate  # noqa: E402
from common.schema import ApprovalDecision  # noqa: E402
from executor import AllowlistedExecutor  # noqa: E402
from rca_agent.graph import run_diagnosis_with_mock  # noqa: E402
from rca_agent.tools.telemetry import dispatch  # noqa: E402
from remediation_planner import draft_plan, next_plan_after_failure  # noqa: E402

from console import real_incident as ri  # noqa: E402
from console.cli.prototype import _load_ground_truth, synthesize_signals  # noqa: E402

FIG_DIR = _ROOT.parent / "295A_Design_Validation" / "figures"
MLX_URL = "http://127.0.0.1:8080/v1"

st.set_page_config(page_title="IR Copilot · 295A Prototype", page_icon="🛟", layout="wide")
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.2rem; max-width: 1180px; }
      div[data-testid="stMetricValue"] { font-size: 1.35rem; }
    </style>
    """,
    unsafe_allow_html=True,
)


def _reset(prefix: str) -> None:
    for key in [k for k in st.session_state if k.startswith(prefix)]:
        del st.session_state[key]


def sidebar() -> None:
    with st.sidebar:
        st.title("295A Prototype")
        st.caption("Calibrated, evidence-verified incident copilot")
        st.divider()
        st.markdown("**Who built which stage**")
        st.markdown(
            "- **Gandham** — infra, telemetry signals, fault scenarios\n"
            "- **Patrini** — baselines (N1), Telemetry Access Layer (N2), LLM agent (N3)\n"
            "- **Peram** — evaluation, planner + approval + executor"
        )
        st.divider()
        st.markdown("**Safety**")
        st.info(
            "Diagnosis is read-only (TAL).\n\n"
            "No write without human approval.\n\n"
            "Executor is allowlisted and **dry-run** here."
        )
        st.session_state.setdefault("operator", "advisor-demo")
        st.session_state.operator = st.text_input("Operator id", st.session_state.operator)
        model = ri.server_model(MLX_URL)
        if model:
            st.success(f"Local LLM online: `{model}`")
        else:
            st.warning("Local LLM offline — saved trajectories will be replayed.")


def plan_approve_execute(prefix: str, incident_id: str, cands, fault_type: str) -> None:
    """Shared plan -> approve -> dry-run execute -> feedback block."""
    if f"{prefix}plan" not in st.session_state:
        if not cands:
            st.error("No candidates — escalate to a human (PB-10).")
            return
        plan = draft_plan(incident_id=incident_id, candidates=cands, fault_type=fault_type)
        gate = ApprovalGate()
        gate.submit(plan)
        st.session_state[f"{prefix}plan"] = plan
        st.session_state[f"{prefix}gate"] = gate
    plan = st.session_state[f"{prefix}plan"]
    gate: ApprovalGate = st.session_state[f"{prefix}gate"]

    st.markdown("#### Remediation plan · playbook lookup (not a second model)")
    left, right = st.columns(2)
    left.markdown(
        f"**Playbook** `{plan.playbook_id}` · **Action** `{plan.action}`  \n"
        f"**Target** `{plan.target_service}` / `{plan.namespace}` · **Risk** `{plan.risk}`"
    )
    right.markdown(f"**Fault** `{plan.fault_type}`  \n**Undo** {plan.undo or '—'}")
    st.caption(plan.rationale)
    if plan.secondary:
        with st.expander("Fallback remedies for candidates 2 and 3"):
            st.dataframe(pd.DataFrame(plan.secondary), width="stretch", hide_index=True)

    a, b = st.columns(2)
    if a.button("Approve plan", key=f"{prefix}approve", type="primary", width="stretch"):
        record = gate.decide(
            plan.id,
            decision=ApprovalDecision.APPROVE,
            operator=st.session_state.operator,
            note="console approval",
        )
        st.session_state[f"{prefix}exec"] = (
            record,
            AllowlistedExecutor(dry_run=True).execute(plan, approval_id=record.id, approved=True),
        )
    if b.button("Reject plan", key=f"{prefix}reject", width="stretch"):
        record = gate.decide(
            plan.id,
            decision=ApprovalDecision.REJECT,
            operator=st.session_state.operator,
            note="console reject",
        )
        st.session_state[f"{prefix}exec"] = (
            record,
            AllowlistedExecutor(dry_run=True).execute(plan, approval_id=record.id, approved=False),
        )

    if f"{prefix}exec" in st.session_state:
        record, result = st.session_state[f"{prefix}exec"]
        if record.decision == ApprovalDecision.APPROVE:
            st.success(f"Approved by **{record.operator}** · audit id `{record.id}`")
        else:
            st.error(f"Rejected by **{record.operator}** — nothing executed · `{record.id}`")
        st.code(result.detail, language="text")
        st.caption(f"Executor status `{result.status}` · dry_run={result.dry_run}")
        if record.decision == ApprovalDecision.APPROVE and st.button(
            "Remedy did not help → plan for the next candidate", key=f"{prefix}fail"
        ):
            plan2 = next_plan_after_failure(
                incident_id=incident_id,
                candidates=cands,
                fault_type=fault_type,
                failed_service=plan.target_service,
            )
            gate.submit(plan2)
            st.session_state[f"{prefix}feedback"] = plan2
        if f"{prefix}feedback" in st.session_state:
            plan2 = st.session_state[f"{prefix}feedback"]
            st.warning(
                f"Feedback loop: new plan `{plan2.playbook_id}` → `{plan2.action}` on "
                f"**{plan2.target_service}**, waiting for a fresh approval."
            )


def tab_real_incident() -> None:
    st.markdown(
        "A real fault from the RCAEval **RE2-OB** benchmark, replayed through the read-only "
        "Telemetry Access Layer. The agent sees an anonymous case id and nothing after *now*."
    )
    cases = ri.demo_cases()
    if not cases:
        st.error("RE2-OB replay data not found under datasets/RCAEval/RE2-OB.")
        return
    labels = {f"Incident {i + 1:02d}": c for i, c in enumerate(cases)}
    choice = st.selectbox(
        "Incident", list(labels), key="ri_choice", on_change=lambda: _reset("ri_run")
    )
    case = labels[choice]
    if st.session_state.get("ri_case") != case:
        st.session_state.ri_case = case
        st.session_state.ri_source = ri.replay(case)
    source = st.session_state.ri_source
    topo = source.topology()

    st.markdown("#### 1 · What the copilot can see (TAL)")
    m1, m2, m3 = st.columns(3)
    m1.metric("Anonymous case id", source.case_id)
    m2.metric(
        "Clock (now, UTC)", datetime.fromtimestamp(source.now(), tz=UTC).strftime("%Y-%m-%d %H:%M")
    )
    m3.metric("Services / call edges", f"{len(topo['services'])} / {len(topo['edges'])}")
    left, right = st.columns([1, 1])
    with left:
        dot = "digraph { rankdir=LR; node [shape=box, style=rounded, fontsize=10];\n"
        dot += "\n".join(f'"{e["caller"]}" -> "{e["callee"]}";' for e in topo["edges"]) + "}"
        st.graphviz_chart(dot, width="stretch")
        st.caption("Call graph built from traces before *now*.")
    with right:
        overview = dispatch(source, "get_metrics", {"start": -600, "end": 0})
        table = pd.DataFrame(overview["metrics"])[
            ["metric", "baseline_mean", "recent_mean", "z_score"]
        ]
        for column in table.columns[1:]:
            table[column] = table[column].map(lambda v: f"{v:.3g}")
        st.dataframe(
            table,
            width="stretch",
            hide_index=True,
            height=320,
        )
        st.caption("Most-changed metrics, last 10 min vs the 10 min before (get_metrics tool).")

    st.markdown("#### 2 · LLM investigation (bounded ReAct, 12 tool calls)")
    model = ri.server_model(MLX_URL)
    c1, c2 = st.columns(2)
    if c1.button(
        "Run local Qwen agent now", type="primary", disabled=model is None, width="stretch"
    ):
        with st.spinner(f"{model} is investigating…"):
            st.session_state.ri_run = ri.run_live(case, MLX_URL, model)
            st.session_state.ri_run_source = f"live run · {model}"
    if c2.button("Replay saved trajectory", width="stretch"):
        saved = ri.saved_trajectory(case)
        if saved is None:
            st.warning("No saved trajectory for this incident.")
        else:
            st.session_state.ri_run = saved
            st.session_state.ri_run_source = f"saved run · {ri.SAVED_RUN}"
    trajectory = st.session_state.get("ri_run")
    if not trajectory:
        return

    st.caption(st.session_state.get("ri_run_source", ""))
    steps = pd.DataFrame(
        [
            {
                "turn": s["turn"],
                "tool": s["tool"],
                "arguments": str(s["arguments"]),
                "valid": "yes" if s["valid"] else "no",
                "evidence": s["evidence_id"],
                "latency_s": s["latency_s"],
            }
            for s in trajectory["steps"]
            if s.get("tool")
        ]
    )
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Status", trajectory["status"])
    k2.metric("Tool calls", trajectory["tool_calls"])
    k3.metric("Invalid calls", trajectory["invalid_tool_calls"])
    k4.metric("Claims without valid evidence", trajectory["unsupported_claims"])
    st.dataframe(steps, width="stretch", hide_index=True)
    st.markdown(
        "**Ranked root-cause candidates:** "
        + " → ".join(f"`{s}`" for s in trajectory["top_services"])
    )
    for claim in trajectory["claims"]:
        st.markdown(
            f"- **{claim.get('service')}** — {claim.get('claim')} "
            f"_(evidence: {', '.join(claim.get('evidence_refs', []))})_"
        )
    with st.expander("Raw tool results (evidence)"):
        for message in trajectory["messages"]:
            if message["role"] == "tool":
                st.code(message["content"][:3000], language="json")

    st.markdown("#### 3 · Plan → approve → dry-run execute")
    cands = ri.candidates(trajectory)
    top = cands[0].service if cands else "—"
    fault, metric = ri.fault_hint(trajectory, top)
    st.caption(
        f"Fault family inferred from evidence: `{fault}` (strongest metric for {top}: "
        f"`{metric}`). Calibrated confidence sets are Phase 1 work."
    )
    plan_approve_execute("ri_run_", source.case_id, cands, fault)

    st.markdown("#### 4 · Reveal the answer")
    if st.toggle("Show ground truth and baselines for this incident", key="ri_run_reveal"):
        service, true_fault = ri.truth(case)
        hit = (trajectory["top_services"] or [None])[0] == service
        st.metric(
            "True root cause",
            f"{service} ({true_fault})",
            delta="agent top-1 correct" if hit else "agent top-1 wrong",
            delta_color="normal" if hit else "inverse",
        )
        rows = [{"method": "LLM agent", "top-5": " → ".join(trajectory["top_services"])}]
        rows += [
            {"method": m, "top-5": " → ".join(r)} for m, r in ri.baseline_rankings(case).items()
        ]
        st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def tab_scripted() -> None:
    st.markdown("Synthetic scenario from `scenarios/registry.yaml` through the full pipeline.")
    scenario = st.selectbox(
        "Fault scenario",
        ["cpu-stress", "pod-crash"],
        key="sc_scenario",
        on_change=lambda: _reset("sc_run"),
    )
    if st.button("Run diagnosis", type="primary"):
        _reset("sc_run")
        gt = _load_ground_truth(scenario)
        signals = synthesize_signals(gt)
        st.session_state.sc_run = (gt, signals, run_diagnosis_with_mock(signals))
    if "sc_run" not in st.session_state:
        return
    gt, signals, diag = st.session_state.sc_run
    if not diag.incident or not diag.candidates:
        st.error("No candidates produced.")
        return
    truth = gt["root_cause_service"]
    m1, m2, m3 = st.columns(3)
    m1.metric("Signals", len(signals))
    m2.metric("Top-1 service", diag.candidates[0].service)
    m3.metric("Ground truth", truth)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "rank": c.rank,
                    "service": c.service,
                    "score": round(c.score, 3),
                    "confidence": round(c.confidence, 3),
                }
                for c in diag.candidates
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    st.caption(f"Agent states: {' → '.join(diag.states)} (mock LLM in this path)")
    plan_approve_execute(
        "sc_run_", diag.incident.id, diag.candidates, str(gt.get("fault_type", "unknown"))
    )


def _fmt(row: dict, metric: str) -> str:
    return f"{row[metric]:.2f} [{row[metric + '_lo']:.2f}, {row[metric + '_hi']:.2f}]"


def tab_baselines() -> None:
    report = ri.n1_results()
    if not report:
        st.info("Run `uv run python -m eval.rcaeval.n1_report` first.")
        return
    st.markdown(
        f"RE2-OB, **{report['n_cases']} cases**, service level, mean [95% bootstrap CI]. "
        "Official rows come from RCAEval's own `main.py` at a pinned commit; our scorer "
        "reproduces its printed Avg@5 exactly."
    )
    rows = []
    for entry in report["methods"].values():
        row = entry["table"]["all"]
        rows.append(
            {
                "method": entry["label"],
                "source": entry["source"],
                "cases": entry["n_predicted"],
                **{m: _fmt(row, m) for m in ("AC@1", "AC@3", "Avg@5")},
            }
        )
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.markdown(
        "**Why our old BARO said 0.30:** our harness called BARO without RCAEval's `dataset` "
        "argument. Run exactly as upstream, BARO scores 0.14, and redis dominance is a property "
        "of BARO on this data, not of our preprocessing: it puts `redis_diskio` first in 77/90 "
        "cases. That metric is "
        "0 for most of the normal period, so its IQR is 0, RobustScaler divides by 1, and any "
        "write burst scores a z of ~10⁴. Dropping zero-IQR metrics (diagnostic only) lifts "
        "BARO to 0.81 — a fairer bar for Phase 1."
    )


def tab_agent_eval() -> None:
    runs = ri.run_summaries()
    if not runs:
        st.info("Run `bash scripts/run_n3_mac.sh` first.")
        return
    table = pd.DataFrame(
        [
            {
                "run": r["run"],
                "model": r["model"],
                "prompt": r.get("prompt"),
                "cases": r["n_cases"],
                "AC@1": round(r["ac1"], 2),
                "AC@3": round(r["ac3"], 2),
                "valid tool calls": r["valid_tool_call_rate"],
                "s / case": r["mean_seconds_per_case"],
            }
            for r in runs
        ]
    )
    st.dataframe(table, width="stretch", hide_index=True)
    run = st.selectbox("Per-case detail", [r["run"] for r in runs], index=len(runs) - 1)
    chosen = next(r for r in runs if r["run"] == run)
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "case": c["case"],
                    "truth": c["true_service"],
                    "fault": c["fault"],
                    "rank of truth": c["rank_of_truth"],
                    "agent top-3": c["top_services"][:3],
                    "tool calls": c["tool_calls"],
                    "seconds": c["seconds"],
                }
                for c in chosen["cases"]
            ]
        ),
        width="stretch",
        hide_index=True,
    )
    notes = _ROOT / "experiments" / "n3" / "FAILURE_MODES.md"
    if notes.exists():
        with st.expander("Failure-mode notes", expanded=True):
            st.markdown(notes.read_text())


def tab_architecture() -> None:
    st.markdown(
        "**System architecture** (static components) and **processing flow** "
        "(runtime + feedback loop) are drawn separately, as requested."
    )
    a, b = st.columns(2)
    for column, name, title in (
        (a, "system_architecture.png", "System architecture"),
        (b, "processing_flow.png", "Processing flow"),
    ):
        with column:
            st.markdown(f"#### {title}")
            path = FIG_DIR / name
            if path.is_file():
                st.image(str(path), width="stretch")
            else:
                st.info("Figure missing — see 295A_Design_Validation/figures/")


def tab_proves() -> None:
    report = ri.n1_results() or {}
    methods = report.get("methods", {})
    agent = report.get("agent_subset") or {}

    def ac1(key: str) -> str:
        return f"{methods[key]['table']['all']['AC@1']:.2f}" if key in methods else "n/a"

    agent_ac1 = agent.get("tables", {}).get("agent", {}).get("all", {}).get("AC@1")
    nsig_sub = agent.get("tables", {}).get("nsigma", {}).get("all", {}).get("AC@1")
    st.markdown(
        f"""
### What this early prototype demonstrates
1. **Core functionality** — real benchmark incident → read-only telemetry API → open-weight
   LLM agent with tools → playbook plan → human approval → allowlisted dry-run executor.
2. **Basis for 295B** — the same TAL protocol gets a live Prometheus/Loki backend; the agent
   moves to LangGraph; calibrated root-cause sets and an evidence verifier slot in before the plan.
3. **Integration of team work** — one path through every member's components.
4. **Safety** — diagnosis cannot write; nothing executes without an approval record; dry-run.

### Honest numbers (RE2-OB)
- Official RCAEval baselines, 90 cases, AC@1: N-Sigma **{ac1("nsigma")}**, CIRCA
  **{ac1("circa")}**, RCD **{ac1("rcd")}**, PDiagnose **{ac1("pdiagnose")}**,
  BARO **{ac1("baro")}**.
- Local Qwen3-4B agent on 30 cases (one per service x fault): AC@1 **{agent_ac1 or 0:.2f}** vs
  N-Sigma **{nsig_sub or 0:.2f}** on the same cases — the difference is **not** significant yet.
- Every number is still an *oracle-onset* result (the clock comes from the injection time);
  detected onset is Charan's C1 and the next re-run.
"""
    )


def main() -> None:
    sidebar()
    st.markdown("# Incident Copilot · Early Prototype")
    tabs = st.tabs(
        [
            "Real incident (RE2-OB)",
            "Scripted scenario",
            "Baselines (N1)",
            "Agent evaluation (N3)",
            "Architecture vs flow",
            "What this proves",
        ]
    )
    with tabs[0]:
        tab_real_incident()
    with tabs[1]:
        tab_scripted()
    with tabs[2]:
        tab_baselines()
    with tabs[3]:
        tab_agent_eval()
    with tabs[4]:
        tab_architecture()
    with tabs[5]:
        tab_proves()


main()
