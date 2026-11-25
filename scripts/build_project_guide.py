# ruff: noqa: E501
"""Build the complete project guide as a Word document.

    uv run --with python-docx python scripts/build_project_guide.py

Writes docs/Incident_Copilot_Complete_Guide.docx.
"""

from __future__ import annotations

from pathlib import Path

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

REPO = Path(__file__).resolve().parents[1]
FIG = REPO / "docs" / "figures"
OUT = REPO / "docs" / "Incident_Copilot_Complete_Guide.docx"
NAVY = RGBColor(0x0B, 0x1F, 0x3A)
TEAL = RGBColor(0x00, 0x7C, 0x7A)

doc = Document()


def setup() -> None:
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)
    for level, size in ((1, 18), (2, 14), (3, 12)):
        style = doc.styles[f"Heading {level}"]
        style.font.name = "Calibri"
        style.font.size = Pt(size)
        style.font.color.rgb = NAVY if level == 1 else TEAL
    for section in doc.sections:
        section.left_margin = section.right_margin = Inches(0.9)
        section.top_margin = section.bottom_margin = Inches(0.8)


def h(text: str, level: int = 1) -> None:
    doc.add_heading(text, level)


def p(text: str, bold_lead: str | None = None) -> None:
    para = doc.add_paragraph()
    if bold_lead:
        para.add_run(bold_lead).bold = True
    para.add_run(text)


def bullets(items: list[str], style: str = "List Bullet") -> None:
    for item in items:
        if item.startswith("**") and "**" in item[2:]:
            lead, rest = item[2:].split("**", 1)
            para = doc.add_paragraph(style=style)
            para.add_run(lead).bold = True
            para.add_run(rest)
        else:
            doc.add_paragraph(item, style=style)


def numbered(items: list[str]) -> None:
    for i, item in enumerate(items, 1):
        para = doc.add_paragraph()
        para.paragraph_format.left_indent = Inches(0.35)
        para.paragraph_format.first_line_indent = Inches(-0.25)
        para.add_run(f"{i}. ")
        if item.startswith("**") and "**" in item[2:]:
            lead, rest = item[2:].split("**", 1)
            para.add_run(lead).bold = True
            para.add_run(rest)
        else:
            para.add_run(item)


def shade(cell, hex_color: str) -> None:
    props = cell._tc.get_or_add_tcPr()
    fill = OxmlElement("w:shd")
    fill.set(qn("w:val"), "clear")
    fill.set(qn("w:color"), "auto")
    fill.set(qn("w:fill"), hex_color)
    props.append(fill)


def table(rows: list[list[str]], widths: list[float] | None = None) -> None:
    t = doc.add_table(rows=len(rows), cols=len(rows[0]))
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            cell = t.cell(r, c)
            cell.text = ""
            run = cell.paragraphs[0].add_run(str(value))
            run.font.size = Pt(9.5)
            if r == 0:
                run.bold = True
                run.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF)
                shade(cell, "0B1F3A")
            elif r % 2 == 0:
                shade(cell, "EEF3F8")
            if widths:
                cell.width = Inches(widths[c])
    doc.add_paragraph()


def image(name: str, caption: str, width: float = 6.5) -> None:
    path = FIG / name
    if not path.exists():
        return
    doc.add_picture(str(path), width=Inches(width))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap = doc.add_paragraph(caption)
    cap.alignment = WD_ALIGN_PARAGRAPH.CENTER
    cap.runs[0].italic = True
    cap.runs[0].font.size = Pt(9)


def code(text: str) -> None:
    para = doc.add_paragraph()
    run = para.add_run(text)
    run.font.name = "Menlo"
    run.font.size = Pt(9)
    para.paragraph_format.left_indent = Inches(0.3)


def title_page() -> None:
    t = doc.add_paragraph()
    t.alignment = WD_ALIGN_PARAGRAPH.CENTER
    t.paragraph_format.space_before = Pt(120)
    run = t.add_run("Agentic Incident-Response Copilot\nfor Production Outages")
    run.bold = True
    run.font.size = Pt(26)
    run.font.color.rgb = NAVY
    s = doc.add_paragraph()
    s.alignment = WD_ALIGN_PARAGRAPH.CENTER
    s.add_run(
        "The complete guide: what the system does, how it works, and what we measured"
    ).italic = True
    for line in (
        "",
        "CMPE 295A · San José State University",
        "Charan Sai Gandham · Venkata Satya Charan Naga Deep Patrini · Vishnu Sree Peram",
        "Advisor: Dr. Bertin Cordova-Diba",
        "November 2026",
    ):
        para = doc.add_paragraph(line)
        para.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_page_break()


def contents() -> None:
    h("Contents")
    numbered(
        [
            "Summary in one page",
            "The problem we are solving",
            "Key ideas and terms",
            "The data: RCAEval RE2-OB",
            "System architecture",
            "Processing flow, step by step",
            "Each component in detail",
            "Walkthrough of a real incident in the website",
            "How we evaluate",
            "Results",
            "What went wrong and what we corrected",
            "Model selection: how and why",
            "Fine-tuning strategy",
            "Literature in brief",
            "Limitations (what the numbers do not show)",
            "How to run everything",
            "Where things live in the code",
            "Questions the professor may ask, with answers",
            "What comes next (295B)",
        ]
    )
    doc.add_page_break()


def summary() -> None:
    h("1. Summary in one page")
    p(
        "When a microservice application fails, operators are flooded with alerts, metrics, logs "
        "and traces. Most of the time goes into finding which service is actually broken. Our "
        "project is a copilot that does that investigation, proposes a fix, and lets a human "
        "decide. It never changes the system on its own."
    )
    p("What the copilot does:", None)
    numbered(
        [
            "Detects an incident from metric changes and error logs.",
            "A local LLM agent (Qwen3-4B) investigates using only read-only tools: metrics, logs "
            "and the service map. It may make at most 12 tool calls.",
            "It returns a ranked list of suspect services. Every claim must cite a tool result.",
            "A planner maps the top suspect and its fault type to a pre-approved playbook action.",
            "A human approves or rejects. Only then does the executor act, and only with "
            "allowlisted actions (dry-run in this prototype).",
            "If the fix does not work, that suspect is ruled out and the next suspect gets a new "
            "plan, which again needs approval.",
        ]
    )
    p("What we measured on 90 real fault injections from the public RCAEval benchmark:", None)
    table(
        [
            ["Component", "Result"],
            [
                "Best official baseline (N-Sigma)",
                "0.79 of incidents: true cause ranked first (AC@1)",
            ],
            [
                "Our LLM agent, 30 incidents",
                "0.93 AC@1, 100% valid tool calls, 8.3 s, $0 per incident",
            ],
            [
                "Planner, same 30 incidents",
                "93% first plan targets the right service; 100% fixed within 3 approvals",
            ],
            ["Weak spot", "Fault type (which fix) right only 57% of the time"],
        ],
        [2.6, 4.0],
    )
    p(
        "The agent beats every baseline on the same 30 cases, but its lead over N-Sigma (+0.10) "
        "is not yet statistically significant. All numbers assume we know when the fault started, "
        "so they are upper bounds.",
        "Honest caveat. ",
    )
    p(
        "A website (make web, http://127.0.0.1:8090) shows the whole flow on real incidents: "
        "error, LLM investigation, root-cause report, fix, human approval, execution, verification "
        "and the feedback loop.",
        "Demo. ",
    )
    doc.add_page_break()


def problem() -> None:
    h("2. The problem we are solving")
    p(
        "Modern applications are split into many small services (microservices) that call each "
        "other over the network. Google's Online Boutique demo shop, which we use, has about a "
        "dozen: frontend, cart, checkout, payment, currency, product catalog, recommendations, "
        "email, shipping, ads and a Redis cache."
    )
    p(
        "When one service breaks, the failure spreads. If the product catalog becomes slow, the "
        "recommendation service that calls it also becomes slow, and so does the frontend that "
        "calls both. Every one of them raises alerts. The operator on call has to work out which "
        "service is the cause and which are just victims. This is called root cause analysis "
        "(RCA), and the time it takes drives how long the outage lasts."
    )
    p("Why this is hard:", None)
    bullets(
        [
            "**Alert storms.** One fault triggers dozens of alerts across many services.",
            "**Symptoms look like causes.** A caller waiting on a slow dependency looks just as "
            "slow as the dependency itself.",
            "**Too much data.** Thousands of metrics, millions of log lines and traces.",
            "**Fixing is risky.** An automatic fix on the wrong service can make the outage worse.",
        ]
    )
    p(
        "Our approach: let an AI do the tedious investigation, but keep it read-only, make it "
        "show its evidence, restrict fixes to a playbook of known-safe actions, and require a "
        "human to approve every change."
    )


def concepts() -> None:
    h("3. Key ideas and terms")
    table(
        [
            ["Term", "Meaning in this project"],
            [
                "Telemetry",
                "Data a running system emits: metrics (numbers over time such as CPU, "
                "memory, latency), logs (text lines) and traces (records of one request hopping "
                "between services).",
            ],
            [
                "Root cause service",
                "The service where the fault was injected. The benchmark tells "
                "us this, so we can score answers.",
            ],
            [
                "Fault types",
                "cpu (CPU stress), mem (memory pressure), disk (disk I/O stress), "
                "socket (connection exhaustion), delay (network delay), loss (packet loss).",
            ],
            [
                "z-score",
                "How unusual a metric is now compared with before: (mean now − mean "
                "before) / spread before. z = 100 means a huge change.",
            ],
            [
                "LLM agent",
                "A language model that can call tools, read the results and decide "
                "what to look at next, instead of answering in one shot.",
            ],
            [
                "ReAct",
                "Reason + Act: the agent alternates between thinking and calling a tool, "
                "until it is confident.",
            ],
            [
                "Evidence id",
                "Every tool result gets a label (E1, E2, …). Claims must cite these, "
                "so a human can check them.",
            ],
            [
                "Playbook",
                "A table of pre-approved fixes, e.g. 'CPU problem → raise CPU limit or "
                "scale out'. The AI cannot invent new actions.",
            ],
            [
                "Dry-run",
                "The executor prints exactly what it would do but does not touch the cluster.",
            ],
            [
                "AC@1 / AC@3",
                "Fraction of incidents where the true cause is ranked 1st / in the top 3.",
            ],
            ["Avg@5", "Average of AC@1 … AC@5; rewards getting the cause near the top."],
            [
                "95% CI",
                "Confidence interval from bootstrap resampling: the range the true score "
                "plausibly lies in given only 90 (or 30) cases.",
            ],
            [
                "Paired bootstrap",
                "Compares two methods on the same cases by resampling cases; "
                "tells us whether a difference is real or luck.",
            ],
            [
                "Oracle onset",
                "We set 'now' to the known fault start + 300 s. Real systems must "
                "detect the start themselves, so our numbers are upper bounds.",
            ],
            [
                "Leakage",
                "Any way the agent could see the answer (case name, labels, future data). "
                "We prevent it and test for it.",
            ],
        ],
        [1.6, 5.0],
    )


def data() -> None:
    h("4. The data: RCAEval RE2-OB")
    p(
        "RCAEval (Pham et al., WWW 2025) is a public benchmark of 735 fault injections into three "
        "microservice systems. We use the RE2-OB suite: 90 injections into Online Boutique."
    )
    bullets(
        [
            "**5 target services:** checkoutservice, currencyservice, emailservice, "
            "productcatalogservice, recommendationservice.",
            "**6 fault types:** cpu, mem, disk, socket, delay, loss.",
            "**3 repetitions** of each combination: 5 × 6 × 3 = 90 cases.",
            "**Per case:** metrics.parquet (Prometheus-style time series), logs.parquet, "
            "traces.parquet, and inject_time.txt (when the fault started).",
        ]
    )
    p(
        "The website and the 30-case agent run use one case per service × fault (repetition 1), "
        "so every combination appears once. In the website they are shown only as INC-2401 … "
        "INC-2430 so the answer is hidden."
    )
    p(
        "Why a public benchmark: the professor asked for data showing the system works. A public "
        "benchmark with known answers lets anyone reproduce our numbers and compare with "
        "published methods, instead of a dataset we built ourselves."
    )


def architecture() -> None:
    h("5. System architecture")
    p(
        "The architecture shows what exists: the components, their boundaries, and who owns them. "
        "It is deliberately drawn separately from the processing flow (next section), which shows "
        "what happens over time. The professor asked us to separate these two."
    )
    image("system_architecture.png", "Figure 1. System architecture (static components)")
    table(
        [
            ["Component", "Responsibility", "Owner"],
            [
                "Telemetry gateway / collectors",
                "Collect metrics, logs, events from the live cluster",
                "Gandham",
            ],
            [
                "Telemetry Access Layer (TAL)",
                "Read-only, leakage-safe access to telemetry; replays RCAEval cases",
                "Patrini",
            ],
            [
                "Correlation engine",
                "Group alerts into incidents; rank suspects without an LLM",
                "Patrini",
            ],
            [
                "RCA agent",
                "LLM investigation with read-only tools; ranked suspects + cited claims",
                "Patrini",
            ],
            [
                "Remediation planner",
                "Map diagnosis to a playbook action, alternatives, feedback loop",
                "Peram",
            ],
            [
                "Approval service",
                "Record human approval / rejection with operator and note",
                "Peram",
            ],
            ["Executor", "The only write path; allowlisted actions; dry-run by default", "Peram"],
            ["Web console", "Operator UI for the whole flow", "Patrini"],
        ],
        [1.9, 3.6, 1.0],
    )
    p(
        "The safety boundary is simple: everything above the approval service can only read. "
        "Only the executor can write, and it refuses anything without an approval record, outside "
        "the allowlist, or outside the allowed namespace."
    )


def flow() -> None:
    h("6. Processing flow, step by step")
    image(
        "processing_flow.png", "Figure 2. Processing flow (runtime sequence with the feedback loop)"
    )
    numbered(
        [
            "**Alert.** Metric changes and error logs indicate an incident. The website shows the "
            "strongest changes and the frontend latency.",
            "**Investigate.** The agent gets an anonymous incident id and the current time. It "
            "calls tools: usually an overview of the most-changed metrics first, then a closer "
            "look at 2–3 suspect services, their logs, and the service map.",
            "**Report.** It returns top_services (ranked) and claims, each citing evidence ids.",
            "**Plan.** The planner takes the top suspect, works out the fault type from the "
            "cited metrics, and looks up the playbook. It shows one primary remedy plus "
            "alternatives for suspects 2 and 3.",
            "**Approve.** A human reads the evidence and approves or rejects. Approval needs an "
            "operator id, a note and an explicit confirmation.",
            "**Execute.** The executor runs the allowlisted action, in dry-run here.",
            "**Verify.** Did the service recover? If yes, the incident is resolved.",
            "**Feedback loop.** If not (or if rejected), that suspect is ruled out, the planner "
            "proposes a remedy for the next suspect, and it needs a new approval. When suspects "
            "run out or the fault is outside our control (e.g. packet loss), it escalates to a "
            "human.",
        ]
    )
    h("Answers to the professor's flow questions", 2)
    table(
        [
            ["Question", "Answer"],
            [
                "One remedy or several?",
                "One primary remedy for the top suspect, plus alternatives "
                "for ranks 2–3 shown side by side. The operator approves one at a time.",
            ],
            [
                "From top-k with confidence to remedies?",
                "Fault type comes from the evidence (the "
                "top suspect's changed metrics). (fault type) → playbook row → action, parameters, "
                "risk, undo. Unknown faults → escalate.",
            ],
            [
                "What if the remedy fails?",
                "Verification fails → service ruled out → next "
                "suspect's remedy → new approval. Exhausted → escalate. Measured: 100% resolved "
                "within 3 approvals on 30 incidents.",
            ],
            [
                "Why 'restricted' executor?",
                "Even after approval it only runs allowlisted actions "
                "in allowed namespaces, and logs everything.",
            ],
        ],
        [2.0, 4.6],
    )


def components() -> None:
    h("7. Each component in detail")

    h("7.1 Telemetry Access Layer (TAL)", 2)
    p(
        "The agent never touches raw files. It talks to the TAL, which for RCAEval is the "
        "RCAEvalReplay class (libs/telemetry_access). It behaves like a live monitoring system:"
    )
    bullets(
        [
            "**Anonymous id.** The incident is called replay-<random hex>; the case folder name "
            "(which contains the answer) is never shown.",
            "**Clock.** 'Now' is the fault start + 300 s. Nothing after now can be read.",
            "**Prometheus-shaped metrics, logs, and a topology** built from traces seen before now.",
            "**Leakage tests** in CI check that no case name, label or future data is reachable.",
        ]
    )

    h("7.2 The three read-only tools", 2)
    table(
        [
            ["Tool", "What it returns"],
            [
                "get_metrics(service?, start, end)",
                "For each metric, the mean in [start, end] vs "
                "the equally long window before, as a z-score. Without a service: the 12 most-changed "
                "metrics across all services (the overview).",
            ],
            [
                "search_logs(service?, pattern?, start, end)",
                "Number of matching log lines now vs "
                "before, per service, plus the most frequent messages.",
            ],
            ["get_topology()", "The service list and caller → callee edges."],
        ],
        [2.4, 4.2],
    )
    p(
        "The tools take a service, not a metric name, so the model cannot invent metrics. A bug "
        "we found: a constant metric (e.g. redis disk I/O = 0) had zero spread and produced "
        "z = 1,000,000. The z-score now floors the spread at 1% of the baseline mean."
    )

    h("7.3 RCA agent (bounded ReAct loop)", 2)
    p(
        "Code: services/rca-agent/rca_agent/llm/react_loop.py. The model is Qwen3-4B (4-bit), "
        "running locally through mlx-lm on a Mac, at temperature 0. The client is "
        "OpenAI-compatible, so any server (Ollama, vLLM, hosted APIs) works."
    )
    bullets(
        [
            "**Rules in the system prompt:** read only through tools; compare recent minutes with "
            "the period before; cite evidence ids; at most 12 tool calls; reply with JSON "
            "{top_services, claims}.",
            "**Prompt v2 procedure:** (1) overview of all metrics over the last 10 minutes; "
            "(2) drill into the 2–3 services whose own metrics changed most, and search their "
            "logs; (3) use the topology to separate the cause from callers that are only slow "
            "because a dependency is slow; (4) rank by how directly their own metrics changed.",
            "**Checks:** invalid tool calls, unknown services, claims citing non-existent "
            "evidence, and JSON repair are all counted.",
        ]
    )
    p(
        "Why prompt v2: with the plain v1 prompt the model anchored on services named in the "
        "prompt and used a 60-second window that lay entirely inside the fault, so every z-score "
        "was near zero. Accuracy went from 0.20 (v1) to 0.80 (v2) on the same 5 cases."
    )

    h("7.4 Correlation engine and baselines", 2)
    p(
        "The correlation engine groups alerts in a time window using the dependency graph and "
        "scores services by severity (0.45), upstreamness (0.30) and earlier onset (0.25). It "
        "works even if the LLM is down. For research comparison we ran the official RCAEval "
        "implementations of eight methods:"
    )
    bullets(
        [
            "**N-Sigma:** ranks metrics by how many standard deviations they moved. Simple and strong.",
            "**BARO:** Bayesian change-point detection with robust (median/IQR) scores.",
            "**CIRCA, RCD:** use causal graphs between metrics.",
            "**PDiagnose:** combines metrics, logs and traces.",
            "**E-Diagnosis, Multi-source BARO, Random:** further references.",
        ]
    )

    h("7.5 Remediation planner", 2)
    p("Code: services/remediation-planner. The playbook (remediation_playbook.yaml):")
    table(
        [
            ["Id", "Fault", "Primary action", "Alternate", "Risk"],
            ["PB-01", "pod_crash", "restart_pod", "—", "low"],
            ["PB-02", "cpu", "set_cpu_limit", "scale_deployment", "medium"],
            ["PB-03", "mem", "set_memory_limit", "restart_pod", "medium"],
            ["PB-04", "delay", "restart_pod", "escalate_manual", "medium"],
            ["PB-05", "loss", "escalate_manual", "restart_pod", "high"],
            ["PB-06", "disk", "restart_pod", "escalate_manual", "medium"],
            ["PB-07", "socket", "restart_pod", "scale_deployment", "medium"],
            ["PB-08", "bad_deploy", "rollback_deployment", "—", "medium"],
            ["PB-09", "functional (RE3)", "rollback_deployment", "escalate_manual", "high"],
            ["PB-10", "unknown", "escalate_manual", "—", "high"],
        ],
        [0.6, 1.3, 1.7, 1.7, 0.7],
    )
    p(
        "Fault type rule (resource-first): latency rises under every fault, so it is a symptom. "
        "If a CPU, memory, disk or socket metric of the suspect moved more than 3 standard "
        "deviations, the strongest of those decides the fault type; otherwise latency → delay. "
        "This raised fault-type accuracy from 38% to 52% on all 90 cases."
    )

    h("7.6 Approval gate and executor", 2)
    bullets(
        [
            "**ApprovalGate:** submit(plan) → decide(approve/reject, operator, note) → audit log "
            "entry with an approval id.",
            "**AllowlistedExecutor(dry_run=True):** refuses without an approval id, refuses "
            "actions not in the allowlist, refuses namespaces outside online-boutique, and "
            "returns a dry-run description of the kubectl action.",
        ]
    )

    h("7.7 Web console", 2)
    p(
        "Backend: console/web_app.py (FastAPI). Frontend: console/web (plain HTML, CSS and "
        "JavaScript, no build step, works offline). The agent runs in a background thread and "
        "the page polls every 0.7 s, so steps appear as they happen."
    )
    table(
        [
            ["Endpoint", "Purpose"],
            ["GET /api/incidents", "The 30-incident queue (anonymous labels)"],
            ["POST /api/incidents/{i}/open", "Build the alert, service map and signal charts"],
            ["POST /api/sessions/{id}/investigate", "Run the live agent or replay the saved run"],
            [
                "POST /api/sessions/{id}/decision",
                "Approve or reject (operator required) → executor",
            ],
            ["POST /api/sessions/{id}/verify", "Recovered / not recovered → resolve or replan"],
            ["POST /api/sessions/{id}/replan", "Propose the next suspect's remedy"],
            ["POST /api/sessions/{id}/reveal", "Ground truth and baseline rankings"],
            ["GET /api/evaluation", "All result tables for the Evaluation page"],
        ],
        [2.6, 4.0],
    )
    p(
        "Incident status moves through: detected → investigating → awaiting approval → "
        "verifying → resolved, or rejected / escalated."
    )


def walkthrough() -> None:
    h("8. Walkthrough of a real incident in the website")
    p(
        "INC-2401 is a real RE2-OB case (CPU stress on checkoutservice, revealed only at the end). "
        "This is what happened in a live run with Qwen3-4B."
    )
    image("web_incident.png", "Figure 3. Incident opened: alert, symptoms, service map, signals")
    p("Steps 1–3 (what broke):", None)
    bullets(
        [
            "The alert lists the metrics that changed most in the last 10 minutes versus the 10 "
            "minutes before, plus error-log counts.",
            "The service map is built from traces; after the investigation the agent's suspects "
            "are highlighted as #1, #2, #3.",
            "Signal charts show the last 20 minutes with the analysis window shaded and the "
            "alert time dashed.",
        ]
    )
    image(
        "web_investigation.png", "Figure 4. LLM investigation (left) and root-cause report (right)"
    )
    p("Step 4, the investigation (5 tool calls, 7.6 s):", None)
    numbered(
        [
            "get_metrics over all services → 12 metrics, strongest change checkoutservice_cpu "
            "(z = 114.6). Evidence E1.",
            "get_topology → 12 services, 9 call edges. E2.",
            "get_metrics for checkoutservice → its own metrics confirm CPU. E3.",
            "search_logs for timeouts in checkoutservice → none. E4.",
            "search_logs for productcatalogservice → none. E5.",
        ]
    )
    p(
        "Step 5, the report: #1 checkoutservice, #2 redis-cart, #3 productcatalogservice. Each "
        "claim cites E1/E3/E5. Confidence is rank-based (1/rank), not calibrated; calibrated "
        "confidence is Phase 1 work."
    )
    image(
        "web_approval_audit.png", "Figure 5. Plan, approval, dry-run, verification and audit trail"
    )
    p("Steps 6–9:", None)
    bullets(
        [
            "**Plan:** PB-02 set_cpu_limit on deploy/checkoutservice, parameters scale_factor 2, "
            "risk medium, undo restore_previous_resources; alternatives scale_deployment for "
            "redis-cart and productcatalogservice. Policy chips confirm allowlisted action, "
            "allowlisted namespace, approval required, dry-run executor.",
            "**Approve:** the operator enters a name and note and confirms. Approval id recorded.",
            "**Execute:** 'DRY-RUN: would run set_cpu_limit on deploy/checkoutservice in "
            "online-boutique with params {scale_factor: 2}'.",
            "**Verify:** recovered (simulated from the benchmark label in replay mode) → resolved "
            "after 1 approved attempt.",
            "**Audit trail:** agent started, ranked, planner mapped, operator approved, executor "
            "ran, verifier confirmed, with timestamps.",
            "**Reveal:** true cause checkoutservice / cpu; the agent ranked it #1, as did N-Sigma "
            "and CIRCA.",
        ]
    )
    p(
        "To see the feedback loop, click Reject (or 'Not recovered'): the planner rules out the "
        "service and proposes a remedy for suspect #2, which needs a new approval."
    )


def evaluation_methods() -> None:
    h("9. How we evaluate")
    p(
        "Each component is evaluated on its own, then the whole pipeline. The professor asked "
        "for methods and metrics per component."
    )
    table(
        [
            ["Component", "What 'correct' means", "Metrics", "Status"],
            [
                "Telemetry Access Layer",
                "Agent cannot see the answer or the future",
                "Leakage tests",
                "Done, in CI",
            ],
            [
                "Baselines",
                "Reference performance",
                "AC@1/3/5, Avg@5, 95% CI",
                "Done (official code)",
            ],
            [
                "RCA agent",
                "True cause ranked high, honest evidence",
                "AC@k, paired bootstrap, valid calls, unsupported claims, seconds, $",
                "Measured (30 cases)",
            ],
            [
                "Planner",
                "Right service and right fix type",
                "Target %, fault type %, resolved within k approvals, wrong-target proposals",
                "Measured (30 + 90 cases)",
            ],
            [
                "Approval / executor",
                "No write without approval; allowlist only",
                "Unsafe-action rate = 0",
                "Implemented (dry-run)",
            ],
            [
                "Whole pipeline",
                "Faster, correct recovery",
                "AC@k, time to root cause, recovery, cost",
                "Offline now; human study in 295B",
            ],
        ],
        [1.4, 1.8, 2.2, 1.2],
    )
    p(
        "Scoring: we ran the unmodified RCAEval main.py for baselines at a pinned commit; our "
        "scorer reproduces its Avg@5 exactly. Agent runs were also scored by RCAEval's own "
        "rcaeval-agent evaluate, which matched our scores. Per-method confidence intervals use "
        "2,000 bootstrap resamples of cases; paired agent-vs-baseline comparisons use 10,000."
    )


def results() -> None:
    h("10. Results")
    h("10.1 Baselines on 90 RE2-OB cases (official RCAEval code)", 2)
    table(
        [
            ["Method", "AC@1 [95% CI]", "AC@3", "AC@5", "Avg@5"],
            ["N-Sigma", "0.79 [0.70, 0.87]", "0.94", "0.99", "0.91"],
            ["RCD", "0.68 [0.57, 0.77]", "0.73", "0.81", "0.75"],
            ["CIRCA", "0.61 [0.51, 0.71]", "0.89", "0.92", "0.83"],
            ["PDiagnose", "0.38 [0.29, 0.48]", "0.91", "0.99", "0.80"],
            ["Multi-source BARO", "0.17 [0.10, 0.24]", "0.88", "0.97", "0.76"],
            ["BARO", "0.14 [0.08, 0.22]", "0.88", "0.94", "0.74"],
            ["Random ranking", "0.12 [0.06, 0.19]", "0.30", "0.51", "0.31"],
            ["E-Diagnosis", "0.03 [0.00, 0.08]", "0.18", "0.18", "0.14"],
        ],
        [1.8, 1.7, 0.8, 0.8, 0.8],
    )
    h("10.2 LLM agent runs", 2)
    table(
        [
            ["Model", "Prompt", "Cases", "AC@1", "AC@3", "Tool calls (invalid)", "s / case"],
            ["Qwen3-4B-4bit (MLX)", "v1", "5", "0.20", "0.20", "35 (0)", "7.6"],
            ["Qwen3-4B-4bit (MLX)", "v2", "5", "0.80", "1.00", "25 (0)", "8.2"],
            ["qwen2.5-7b-instruct (Ollama)", "v2", "5", "0.60", "1.00", "20 (0)", "10.6"],
            ["Qwen3-4B-4bit (MLX)", "v2", "30", "0.93", "1.00", "152 (0)", "8.3"],
        ],
        [1.9, 0.6, 0.6, 0.6, 0.6, 1.3, 0.7],
    )
    h("10.3 Agent vs baselines on the same 30 incidents", 2)
    table(
        [
            ["Method", "AC@1", "Agent − method [95% CI]"],
            ["LLM agent (Qwen3-4B, v2)", "0.93", "—"],
            ["N-Sigma", "0.83", "+0.10 [−0.07, +0.27]  (not significant)"],
            ["RCD", "0.70", "+0.23 [+0.10, +0.40]"],
            ["CIRCA", "0.57", "+0.37 [+0.13, +0.57]"],
            ["PDiagnose", "0.43", "+0.50 [+0.33, +0.67]"],
            ["BARO", "0.13", "+0.80 [+0.60, +0.93]"],
        ],
        [2.4, 0.8, 3.0],
    )
    image("web_evaluation.png", "Figure 6. Evaluation page: baselines with confidence intervals")
    h("10.4 Planner experiment", 2)
    p(
        "For each of the 30 incidents: take the agent's ranking and cited metrics, derive the "
        "fault type, look up the playbook, and replay the feedback loop (a remedy on the wrong "
        "service fails, that service is ruled out, the next suspect is proposed, new approval)."
    )
    table(
        [
            ["Metric (30 incidents)", "Most-changed rule", "Resource-first rule"],
            ["First plan targets the true service", "93%", "93%"],
            ["Fault type correct", "40%", "57%"],
            ["First plan fully correct (service + playbook)", "37%", "53%"],
            ["Resolved within 1 / 2 / 3 approvals", "93 / 97 / 100%", "93 / 97 / 100%"],
            ["Mean approvals when resolved", "1.10", "1.10"],
            ["Wrong-service proposals per incident", "0.10", "0.10"],
        ],
        [3.2, 1.6, 1.6],
    )
    table(
        [
            [
                "Fault type accuracy, all 90 cases",
                "cpu",
                "mem",
                "disk",
                "socket",
                "delay",
                "loss",
                "all",
            ],
            ["Most-changed metric", "27%", "20%", "67%", "20%", "93%", "0%", "38%"],
            ["Resource-first", "53%", "60%", "67%", "60%", "73%", "0%", "52%"],
        ],
        [2.0, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6, 0.6],
    )
    p(
        "Interpretation: choosing which service to fix works well, and the feedback loop catches "
        "the rest. Choosing which kind of fix is the weak link. Packet loss is indistinguishable "
        "from delay in these metrics; it needs network-error signals or default escalation."
    )
    image("web_planner.png", "Figure 7. Planner results on the Evaluation page")
    h("10.5 Failure modes we observed", 2)
    bullets(
        [
            "**No invalid tool calls in 232 calls.** This is partly by design: tools take a "
            "service name and return small summaries.",
            "**Anchoring (prompt v1):** the model ran the same script on every case and never "
            "looked at the faulty service. Fixed by the overview-first procedure.",
            "**Caller vs callee:** both v2 misses blamed recommendationservice (the caller) for "
            "productcatalogservice delay and loss, because both showed huge latency increases.",
            "**Evidence that exists but does not support the claim:** citing E1 does not mean E1 "
            "says what the claim says. A semantic verifier is Phase 1 work.",
        ]
    )


def corrections() -> None:
    h("11. What went wrong and what we corrected")
    bullets(
        [
            "**BARO 0.30 → 0.14.** Earlier reports said BARO scored 0.30. That came from our own "
            "harness calling BARO without its dataset argument. The official code gives 0.14. "
            "The cause: redis-cart metrics with zero inter-quartile range get enormous robust "
            "scores. A zero-IQR guard (diagnostic only) raises BARO to 0.81.",
            "**N-Sigma 0.856 → 0.79** for the same reason (own harness vs official).",
            "**Tool z-score bug:** constant metrics produced z = 10⁶; fixed by flooring the "
            "spread. The 30-case accuracy was 0.93 before and after.",
            "**Prompt tuned on its own test cases:** v2 was written after reading the v1 runs on "
            "5 cases, so the 30-case run (25 unseen cases) is the fair estimate.",
            "**Fault type rule:** the first rule was right only 38% of the time; the resource-first "
            "rule, with a threshold fixed in advance, gives 52% on all 90 cases.",
        ]
    )


def model_selection() -> None:
    h("12. Model selection: how and why")
    p("We chose the model with measurable criteria, not by brand name:")
    table(
        [
            ["Criterion", "Metric", "Gate", "Qwen3-4B"],
            [
                "Diagnosis quality",
                "AC@1 on the same cases",
                "≥ best baseline",
                "0.93 vs N-Sigma 0.83",
            ],
            ["Tool reliability", "% valid tool calls", "≥ 95%", "100% (152)"],
            ["Evidence honesty", "% claims with existing evidence", "≥ 90%", "100%"],
            ["Latency", "seconds per incident", "interactive", "8.3 s"],
            ["Cost", "$ per incident", "cheapest passing", "$0 (local)"],
            ["Privacy", "runs locally", "required option", "yes"],
        ],
        [1.4, 1.9, 1.3, 2.0],
    )
    p(
        "Rule: pick the cheapest model within 3 points of the best AC@1 that passes every gate. "
        "Qwen3-4B beat qwen2.5-7b on the same 5 cases (0.80 vs 0.60; small sample, direction "
        "only) and passed every gate on 30 cases, so it is the selected backbone. Hosted models "
        "(GPT-4o-mini, Claude Sonnet class) will be tested on the same 30 cases when API budget "
        "is available; one is adopted only if it beats Qwen3-4B by more than 3 points."
    )
    p(
        "Why a small local model: no telemetry leaves the machine, no per-incident cost, and the "
        "literature (e.g. RCABench) shows backbone choice moves accuracy by 10+ points at large "
        "cost differences, so it must be measured."
    )


def fine_tuning() -> None:
    h("13. Fine-tuning strategy (295B plan)")
    p(
        "We do not fine-tune a model to generate fixes: labelled remediation data is scarce and "
        "free-form cluster actions are unsafe, so fixes stay in the playbook. We do plan to "
        "fine-tune the read-only diagnosis agent, because its errors are reasoning errors "
        "(caller vs callee, anchoring) that prompting only partly fixes."
    )
    numbered(
        [
            "**Stage 1, supervised fine-tuning by rejection sampling.** Run the agent (itself, or "
            "a larger Qwen3 14B/32B as teacher) on the Sock Shop and Train Ticket suites (430 "
            "cases), 4 samples each. Keep only runs with the correct answer, all tool calls valid, "
            "all claims supported by their evidence: about 1,000–1,500 trajectories.",
            "**Method: QLoRA.** 4-bit base model, LoRA rank 16, alpha 32 on attention and MLP "
            "layers, learning rate 1e-4, 2–3 epochs, 8k context. Loss only on the model's own "
            "turns, so it learns which tool to call, not to memorise telemetry. Qwen3-8B fits on "
            "one A100-40GB (SJSU HPC); Qwen3-4B also trains on a Mac with mlx-lm.",
            "**Stage 2, preference tuning (DPO).** Pairs of correct and wrong runs on the same "
            "case, targeting caller/callee confusion (prefer checking the callee's own metrics).",
            "**Leakage control.** Split by system: Online Boutique is never used for training, "
            "only for testing. Anonymous ids and clock-clipped telemetry keep answers out of "
            "prompts.",
            "**Gates to replace the base model:** +0.05 AC@1 on held-out RE2-OB with a confidence "
            "interval excluding zero, no regression on other Online Boutique suites, ≥ 99% valid "
            "calls, ≥ 90% semantically supported claims, latency ≤ 1.5× base, no regression on "
            "live Chaos Mesh scenarios.",
        ]
    )


def literature() -> None:
    h("14. Literature in brief")
    table(
        [
            ["Work", "What it shows", "How we use it"],
            [
                "RCAEval (WWW 2025)",
                "Public benchmark, 735 cases, standard baselines",
                "Our evaluation data and baselines",
            ],
            [
                "BARO (FSE 2024), N-Sigma, CIRCA, RCD",
                "Statistical / causal RCA without LLMs",
                "Baselines; LLM must beat them",
            ],
            ["ReAct", "Reason-and-act loop for tool-using LLMs", "Our agent design"],
            [
                "RCACopilot, RCAgent",
                "LLM agents for cloud incidents; tool selection",
                "Inspiration for the read-only agent",
            ],
            [
                "OpenRCA, ITBench, AIOpsLab",
                "Agents still fail many hard SRE tasks",
                "Why humans stay on the write path",
            ],
            [
                "HolmesGPT, K8sGPT",
                "Open-source Kubernetes troubleshooting assistants",
                "Comparators for 295B",
            ],
            [
                "RCABench (2026)",
                "Backbone choice moves accuracy ~79% → 90%",
                "Why model selection is experimental",
            ],
        ],
        [1.9, 2.6, 2.1],
    )
    p(
        "Why agentic instead of one big prompt: the agent fetches only what it needs (small "
        "context), every claim is tied to a tool result (checkable), the statistical ranking "
        "still works if the LLM is down (graceful degradation), and the agent has no write tools "
        "(limited blast radius)."
    )


def limitations() -> None:
    h("15. Limitations (what the numbers do not show)")
    bullets(
        [
            "**Oracle onset.** 'Now' is the known fault start + 300 s; a real system must detect "
            "the start. All numbers are upper bounds.",
            "**Small samples.** 30 agent cases; the lead over N-Sigma is not significant. "
            "The model comparison used only 5 cases.",
            "**One system.** Only Online Boutique so far.",
            "**Simulated recovery.** In the website, 'recovered' means the remedy targeted the "
            "true service (benchmark label). Live recovery after a real action is 295B.",
            "**Evidence check is shallow.** We check that cited ids exist, not that they support "
            "the claim.",
            "**Fault type is weak.** 57% on the 30 cases; packet loss 0%.",
            "**Confidence is rank-based,** not calibrated.",
        ]
    )


def how_to_run() -> None:
    h("16. How to run everything")
    p("Prerequisites: macOS or Linux, Python 3.11+, uv, about 1.5 GB disk.")
    code(
        "git clone https://github.com/PeramVishnuSree/Agentic-incident-response-copilot-for-production-outages.git\n"
        "cd Agentic-incident-response-copilot-for-production-outages\n"
        "uv sync --dev          # install\n"
        "make data              # download the 90 RE2-OB cases (once)\n"
        "make web               # open http://127.0.0.1:8090"
    )
    p("Optional, for live LLM investigations (otherwise use 'Replay recorded run'):")
    code(
        "# Apple Silicon\n"
        "uv tool install mlx-lm\n"
        "mlx_lm.server --model mlx-community/Qwen3-4B-4bit --host 127.0.0.1 --port 8080\n\n"
        "# Any OS with Ollama\n"
        "ollama pull qwen2.5:7b-instruct\n"
        "export COPILOT_LLM_URL=http://127.0.0.1:11434/v1"
    )
    table(
        [
            ["Command", "What it does"],
            ["make web", "The website"],
            ["make prototype-ui", "Earlier Streamlit console (port 8501)"],
            ["uv run pytest", "76 tests"],
            ["make n1-report", "Baseline table with confidence intervals"],
            ["make rcaeval-official", "Re-run official baselines (needs ../external/RCAEval)"],
            ["make n3-smoke", "Run the LLM agent on RE2-OB cases"],
            ["make planner-eval", "Planner experiment"],
            ["make prototype", "Command-line version of the pipeline"],
            ["make help", "All commands"],
        ],
        [2.2, 4.4],
    )
    p("Troubleshooting:", None)
    bullets(
        [
            "Empty queue: run make data, or set RCAEVAL_DIR to the folder containing RE2-OB/.",
            "'LLM offline': start mlx_lm.server on port 8080 or set COPILOT_LLM_URL.",
            "Port busy: lsof -ti tcp:8090 | xargs kill.",
        ]
    )


def code_map() -> None:
    h("17. Where things live in the code")
    table(
        [
            ["Path", "Contents"],
            ["console/web_app.py, console/web/", "Website backend and frontend"],
            ["console/real_incident.py", "Case loading, saved runs, baselines, fault-type rule"],
            ["libs/telemetry_access/", "Telemetry Access Layer and RCAEval replay"],
            ["services/rca-agent/rca_agent/llm/react_loop.py", "The agent loop and prompts"],
            ["services/rca-agent/rca_agent/tools/telemetry.py", "The three read-only tools"],
            ["services/remediation-planner/", "Playbook YAML and planner"],
            [
                "services/approval-service/, services/executor/",
                "Approval gate and allowlisted executor",
            ],
            ["eval/rcaeval/", "Scoring and the N1 baseline report"],
            ["eval/planner_eval.py", "Planner experiment"],
            ["experiments/n3/", "Saved agent trajectories, run summaries, failure modes"],
            ["eval/artifacts/rcaeval/", "Saved results (official runs, N1, planner)"],
            ["tests/", "Integration tests (web app, real incident, scoring, …)"],
            ["docs/", "Architecture, baselines, prototype guide, figures, this guide"],
        ],
        [3.0, 3.6],
    )


def qa() -> None:
    h("18. Questions the professor may ask, with answers")
    pairs = [
        (
            "Is the LLM actually better than simple statistics?",
            "On the same 30 incidents it scores 0.93 vs N-Sigma 0.83, but the difference is not yet "
            "significant (CI −0.07 to +0.27). It is clearly better than RCD, CIRCA, PDiagnose and "
            "BARO. Beyond accuracy it explains its reasoning with evidence, which the baselines do not.",
        ),
        (
            "Could the agent be cheating by seeing the answer?",
            "No. It sees an anonymous id, no case name or label, and no data after 'now'. Leakage "
            "tests in CI check this on real cases.",
        ),
        (
            "Why did BARO drop from 0.30 to 0.14?",
            "0.30 came from our own harness calling BARO incorrectly. The official code gives 0.14 "
            "because redis-cart metrics with zero spread dominate its robust scores.",
        ),
        (
            "What happens when the remedy does not work?",
            "That service is ruled out, the next suspect gets a plan, and a human must approve again. "
            "On 30 incidents, all were resolved within three approvals; on average 1.1.",
        ),
        (
            "Why a playbook instead of letting the LLM decide the fix?",
            "Safety and auditability. Generated cluster commands could do damage; a playbook of "
            "allowlisted actions with risk and undo is what companies use, and the professor agreed.",
        ),
        (
            "Why Qwen3-4B?",
            "It is the smallest and cheapest model that passed every criterion: 0.93 accuracy, 100% "
            "valid tool calls, 8 s, $0, fully local. It beat qwen2.5-7b on the same cases.",
        ),
        (
            "What is the weakest part?",
            "Choosing the fix type (57%), especially packet loss. Next steps: ask the agent for an "
            "explicit fault label, use network-error signals, or a small classifier.",
        ),
        (
            "Are the numbers realistic?",
            "They are upper bounds because the fault start is known. Replacing it with detected onset "
            "is the next re-run.",
        ),
        (
            "How will you fine-tune?",
            "QLoRA on verified successful trajectories from other systems, then DPO on caller/callee "
            "mistakes, tested only on Online Boutique, with explicit gates (Section 13).",
        ),
        (
            "What does each member own?",
            "Gandham: cluster, observability, telemetry gateway. Patrini: Telemetry Access Layer, "
            "agent, baselines, web console. Peram: scenarios, planner, approval, executor, evaluation.",
        ),
    ]
    for q, a in pairs:
        para = doc.add_paragraph()
        para.add_run("Q: " + q).bold = True
        doc.add_paragraph("A: " + a)


def next_steps() -> None:
    h("19. What comes next (295B)")
    bullets(
        [
            "Detected onset instead of the oracle clock.",
            "Semantic evidence verifier; calibrated confidence.",
            "Better fault-type classification; network signals for packet loss.",
            "Hosted-model arm of the model bakeoff (same 30 cases, 3 repeats).",
            "Fine-tuning per Section 13.",
            "Live executor on the kind cluster with Chaos Mesh faults and real recovery checks.",
            "PostgreSQL incident and audit store.",
            "Comparison with HolmesGPT; harder datasets (other RCAEval suites, OpenRCA).",
            "Human study: time to root cause with vs without the copilot.",
        ]
    )


def main() -> None:
    setup()
    title_page()
    contents()
    summary()
    problem()
    concepts()
    data()
    architecture()
    flow()
    components()
    walkthrough()
    evaluation_methods()
    results()
    corrections()
    model_selection()
    fine_tuning()
    literature()
    limitations()
    how_to_run()
    code_map()
    qa()
    next_steps()
    doc.save(OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
