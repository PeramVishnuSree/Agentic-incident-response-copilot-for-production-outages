"use strict";

const S = { view: "console", incidents: [], session: null, health: null, timer: null, evalData: null };
const $ = (sel) => document.querySelector(sel);
const esc = (x) =>
  String(x ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const fmt = (v, d = 2) => (v === null || v === undefined || Number.isNaN(v) ? "–" : Number(v).toFixed(d));
const sig = (v) => {
  if (v === null || v === undefined) return "–";
  const a = Math.abs(v);
  if (a >= 1e6) return (v / 1e6).toFixed(1) + "M";
  if (a >= 1e3) return (v / 1e3).toFixed(1) + "k";
  if (a >= 10) return v.toFixed(1);
  return v.toPrecision(3);
};
const clock = (ts) => new Date(ts * 1000).toISOString().slice(11, 19) + " UTC";
const zClass = (z) => (Math.abs(z) >= 20 ? "hot" : Math.abs(z) >= 4 ? "warm" : "cool");
const operator = () => $("#operator").value.trim() || "operator";

async function api(path, body) {
  const opts = body === undefined ? {} : { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) };
  const res = await fetch(path, opts);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.detail || res.statusText);
  return data;
}

function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast" + (err ? " err" : "");
  clearTimeout(t._h);
  t._h = setTimeout(() => t.classList.add("hidden"), 3600);
}

/* ---------- navigation ---------- */
document.querySelectorAll("nav button").forEach((b) =>
  b.addEventListener("click", () => {
    S.view = b.dataset.view;
    document.querySelectorAll("nav button").forEach((x) => x.classList.toggle("active", x === b));
    for (const v of ["console", "eval", "arch", "about"]) $("#view-" + v).classList.toggle("hidden", v !== S.view);
    if (S.view === "eval") renderEval();
    if (S.view === "arch") renderArch();
    if (S.view === "about") renderAbout();
  })
);

async function refreshHealth() {
  try {
    S.health = await api("/api/health");
  } catch {
    S.health = { llm_model: null };
  }
  const pill = $("#llm-pill");
  if (S.health.llm_model) {
    pill.className = "pill ok";
    pill.innerHTML = `<span class="dot"></span>LLM online · ${esc(S.health.llm_model.split("/").pop())}`;
  } else {
    pill.className = "pill off";
    pill.innerHTML = `<span class="dot"></span>LLM offline · recorded runs only`;
  }
}

/* ---------- queue ---------- */
async function loadQueue() {
  S.incidents = await api("/api/incidents");
  renderQueue();
}

function renderQueue() {
  const short = { awaiting_approval: "approval", investigating: "running", detected: "open" };
  const statusName = (s) => short[s] || s;
  $("#queue").innerHTML = S.incidents
    .map(
      (i) => `<button class="qitem ${S.session && S.session.label === i.label ? "active" : ""}" data-i="${i.index}">
        <span class="qlabel">${esc(i.label)}</span><span class="status-chip ${esc(i.status)}">${esc(statusName(i.status))}</span></button>`
    )
    .join("");
  document.querySelectorAll(".qitem").forEach((b) => b.addEventListener("click", () => openIncident(+b.dataset.i)));
}

async function openIncident(index) {
  $("#incident").innerHTML = `<div class="empty"><div><div class="dots"><i></i><i></i><i></i></div><p>Opening replay…</p></div></div>`;
  try {
    S.session = await api(`/api/incidents/${index}/open`, {});
    renderIncident();
    syncQueue();
    poll();
  } catch (e) {
    toast(e.message, true);
  }
}

function syncQueue() {
  const s = S.session;
  const item = S.incidents.find((i) => i.label === s.label);
  if (item) item.status = s.status;
  renderQueue();
}

function poll() {
  clearTimeout(S.timer);
  if (!S.session || S.session.agent.status !== "running") return;
  S.timer = setTimeout(async () => {
    try {
      S.session = await api(`/api/sessions/${S.session.id}`);
      renderLive();
      syncQueue();
    } catch (e) {
      toast(e.message, true);
    }
    poll();
  }, 700);
}

async function act(path, body) {
  try {
    S.session = await api(`/api/sessions/${S.session.id}/${path}`, body ?? {});
    renderLive();
    syncQueue();
    poll();
  } catch (e) {
    toast(e.message, true);
  }
}

/* ---------- incident page ---------- */
function renderIncident() {
  const s = S.session;
  $("#incident").innerHTML = `
    <div id="sec-head"></div>
    <div class="card stepper" id="sec-stepper"></div>
    <div class="grid g32">
      <div class="card" id="sec-alert"></div>
      <div class="card topo" id="sec-topo"></div>
    </div>
    <div class="card section" id="sec-signals"></div>
    <div class="grid g2 section">
      <div class="card" id="sec-agent"></div>
      <div class="card" id="sec-rca"></div>
    </div>
    <div class="grid g32 section">
      <div class="card" id="sec-plan"></div>
      <div class="card" id="sec-exec"></div>
    </div>
    <div class="grid g23 section">
      <div class="card" id="sec-audit"></div>
      <div class="card" id="sec-reveal"></div>
    </div>`;
  renderAlert(s);
  renderSignals(s);
  renderLive();
}

function renderLive() {
  const s = S.session;
  renderHead(s);
  renderStepper(s);
  renderTopo(s);
  renderAgent(s);
  renderRca(s);
  renderPlan(s);
  renderExec(s);
  renderAudit(s);
  renderReveal(s);
}

const STATUS_TEXT = {
  detected: ["Alert firing · awaiting investigation", "major"],
  investigating: ["LLM agent investigating", "info"],
  awaiting_approval: ["Remedy proposed · awaiting human approval", "major"],
  rejected: ["Plan rejected by operator", "high"],
  verifying: ["Remedy executed · verifying recovery", "info"],
  resolved: ["Resolved", "ok"],
  escalated: ["Escalated to on-call engineer", "high"],
};

function renderHead(s) {
  const [text, cls] = STATUS_TEXT[s.status] || [s.status, "neutral"];
  $("#sec-head").innerHTML = `<div class="ihead">
    <div>
      <div class="row"><span class="badge ${esc(s.alert.severity)}">${esc(s.alert.severity)}</span>
        <span class="mono muted">${esc(s.label)}</span><span class="badge ${cls}">${esc(text)}</span></div>
      <h1>${esc(s.alert.title)}</h1>
      <div class="meta">
        <span>Alert fired <b>${clock(s.alert.fired_at)}</b></span>
        <span>Now <b>${clock(s.now)}</b></span>
        <span>Case seen by agent <b class="mono">${esc(s.case_id)}</b></span>
        <span title="${esc(s.clock_source)}">Clock: <b>oracle onset + 5 min</b></span>
      </div>
    </div>
    <div class="actions"><button class="btn sm ghost" id="reset-btn">↺ Reset incident</button></div>
  </div>`;
  $("#reset-btn").onclick = async () => {
    S.session = await api(`/api/incidents/${S.incidents.find((i) => i.label === s.label).index}/reset`, {});
    renderIncident();
    syncQueue();
  };
}

function stageStates(s) {
  const names = ["Detect", "Investigate", "Diagnose", "Plan", "Approve", "Execute", "Verify"];
  const order = { detected: 1, investigating: 1, awaiting_approval: 4, rejected: 4, verifying: 6, resolved: 7, escalated: 7 };
  const cur = order[s.status] ?? 1;
  return names.map((n, i) => {
    let st = i < cur ? "done" : i === cur ? "active" : "";
    if (s.status === "rejected" && i === 4) st = "fail";
    if (s.status === "escalated" && i >= 5) st = i === 5 ? "done" : "fail";
    if (s.status === "detected" && i === 1) st = "active";
    return { n, st };
  });
}

function renderStepper(s) {
  const attempts = s.attempts.filter((a) => a.approval.decision === "approve").length;
  $("#sec-stepper").innerHTML =
    stageStates(s)
      .map(
        ({ n, st }, i) => `<div class="stage ${st}"><span class="ring">${st === "done" ? "✓" : st === "fail" ? "!" : i + 1}</span>
        <span class="name">${n}${n === "Execute" && attempts > 1 ? ` <span class="badge info">attempt ${attempts}</span>` : ""}</span><span class="bar"></span></div>`
      )
      .join("");
}

function renderAlert(s) {
  const logs = s.logs || {};
  const slo = s.alert.slo;
  $("#sec-alert").innerHTML = `
    <h3><span class="num">1</span>What broke</h3>
    <p class="sub">Symptoms the monitoring stack sees: largest metric changes in the last 10 min vs the 10 min before, and error logs.</p>
    <div class="alert-box"><div class="t"><span class="siren"></span>${esc(s.alert.title)}</div>
      ${slo ? `<div class="small muted" style="margin-top:6px">SLO signal frontend p90 latency: ${sig(slo.baseline_mean)}s → <b style="color:#fecdd3">${sig(slo.recent_mean)}s</b> (z=${fmt(slo.z_score, 1)})</div>` : ""}
    </div>
    ${s.alert.symptoms
      .map(
        (m) => `<div class="symptom"><span class="mono">${esc(m.metric)}</span>
        <span class="muted">${sig(m.baseline_mean)} → <b style="color:var(--text)">${sig(m.recent_mean)}</b></span>
        <span class="z ${zClass(m.z_score)}">z ${fmt(m.z_score, 1)}</span></div>`
      )
      .join("")}
    <div class="row" style="margin-top:12px"><b class="small">Error / timeout logs (10 min)</b><span class="spacer"></span>
      <span class="small muted">${logs.count ?? 0} lines · baseline ${logs.baseline_count ?? 0}</span></div>
    ${(logs.top_messages || []).slice(0, 3).map((m) => `<div class="logline" title="${esc(m.message)}">${esc(m.count)}× ${esc(m.message)}</div>`).join("") ||
      `<div class="small faint" style="margin-top:6px">No error lines — the failure shows up in metrics only, which is common for resource faults.</div>`}`;
}

function layoutTopology(topo) {
  const services = topo.services || [];
  const edges = topo.edges || [];
  const incoming = {};
  services.forEach((n) => (incoming[n] = 0));
  edges.forEach((e) => (incoming[e.callee] = (incoming[e.callee] || 0) + 1));
  const connected = new Set(edges.flatMap((e) => [e.caller, e.callee]));
  const depth = {};
  const roots = services.filter((n) => connected.has(n) && !incoming[n]);
  const queue = roots.map((r) => [r, 0]);
  while (queue.length) {
    const [n, d] = queue.shift();
    if (depth[n] !== undefined && depth[n] >= d) continue;
    depth[n] = d;
    edges.filter((e) => e.caller === n).forEach((e) => d < 6 && queue.push([e.callee, d + 1]));
  }
  const maxD = Math.max(0, ...Object.values(depth));
  services.filter((n) => depth[n] === undefined).forEach((n) => (depth[n] = maxD + 1));
  const cols = {};
  services.forEach((n) => (cols[depth[n]] = cols[depth[n]] || []).push(n));
  const W = 560, colW = W / (Object.keys(cols).length || 1), nodeH = 26;
  const H = Math.max(...Object.values(cols).map((c) => c.length)) * 38 + 20;
  const pos = {};
  Object.entries(cols).forEach(([d, list]) => {
    list.sort();
    list.forEach((n, i) => (pos[n] = { x: d * colW + 8, y: ((i + 0.5) * H) / list.length - nodeH / 2, w: Math.min(colW - 18, 150), h: nodeH }));
  });
  return { pos, edges, W, H, isolatedCol: maxD + 1, hasIsolated: services.some((n) => !connected.has(n)) };
}

function renderTopo(s) {
  const { pos, edges, W, H, hasIsolated } = layoutTopology(s.topology);
  const ranks = {};
  (s.diagnosis?.candidates || []).slice(0, 3).forEach((c) => (ranks[c.service] = "r" + c.rank));
  const failed = new Set(s.attempts.filter((a) => a.verification && !a.verification.recovered).map((a) => a.target));
  const anom = new Set(s.alert.symptoms.map((m) => m.metric.split("_")[0]));
  const truth = s.revealed?.service;
  const nodeCls = (n) => {
    const base = n.replace("-cart", "");
    return ["node", ranks[n] || "", failed.has(n) ? "failed" : "", anom.has(base) ? "anom" : "", truth === n ? "truth" : ""].join(" ");
  };
  const lines = edges
    .filter((e) => pos[e.caller] && pos[e.callee])
    .map((e) => {
      const a = pos[e.caller], b = pos[e.callee];
      const x1 = a.x + a.w, y1 = a.y + a.h / 2, x2 = b.x, y2 = b.y + b.h / 2, mx = (x1 + x2) / 2;
      return `<path class="edge" marker-end="url(#arr)" d="M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2 - 3},${y2}"/>`;
    })
    .join("");
  const nodes = Object.entries(pos)
    .map(([n, p]) => `<g class="${nodeCls(n)}"><rect x="${p.x}" y="${p.y}" width="${p.w}" height="${p.h}"/>
      <text x="${p.x + p.w / 2}" y="${p.y + 17}" text-anchor="middle">${esc(n.length > 22 ? n.slice(0, 21) + "…" : n)}</text></g>`)
    .join("");
  $("#sec-topo").innerHTML = `<h3><span class="num">2</span>Service map</h3>
    <p class="sub">Built by the TAL from distributed traces observed before <i>now</i>${hasIsolated ? "; right column = no traced calls" : ""}.</p>
    <svg viewBox="0 0 ${W} ${H}"><defs><marker id="arr" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L10,5 L0,10 z" fill="#33456b"/></marker></defs>${lines}${nodes}</svg>
    <div class="legend"><span><i style="background:var(--red)"></i>agent rank 1</span><span><i style="background:var(--orange)"></i>rank 2</span>
      <span><i style="background:var(--amber)"></i>rank 3</span><span><i style="border:1px dashed #94a3b8"></i>ruled out by feedback</span>
      ${truth ? `<span><i style="background:var(--green)"></i>ground truth</span>` : ""}</div>`;
}

function sparkline(series, now) {
  const pts = series.points;
  if (!pts.length) return "";
  const W = 260, H = 70, t0 = now - 1200;
  const vals = pts.map((p) => p[1]);
  let lo = Math.min(...vals), hi = Math.max(...vals);
  if (hi === lo) { hi += 1; lo -= 1; }
  const x = (t) => ((t - t0) / 1200) * W;
  const y = (v) => H - 6 - ((v - lo) / (hi - lo)) * (H - 12);
  const d = pts.map((p, i) => `${i ? "L" : "M"}${x(p[0]).toFixed(1)},${y(p[1]).toFixed(1)}`).join(" ");
  const area = `${d} L${x(pts[pts.length - 1][0]).toFixed(1)},${H} L${x(pts[0][0]).toFixed(1)},${H} Z`;
  const id = "g" + Math.random().toString(36).slice(2, 8);
  return `<svg viewBox="0 0 ${W} ${H}" preserveAspectRatio="none">
    <defs><linearGradient id="${id}" x1="0" x2="0" y1="0" y2="1"><stop offset="0" stop-color="#7c8cff" stop-opacity=".35"/><stop offset="1" stop-color="#7c8cff" stop-opacity="0"/></linearGradient></defs>
    <rect x="${x(now - 600)}" y="0" width="${W - x(now - 600)}" height="${H}" fill="rgba(244,63,94,.07)"/>
    <line x1="${x(now - 300)}" x2="${x(now - 300)}" y1="0" y2="${H}" stroke="#f43f5e" stroke-dasharray="3 3" stroke-width="1"/>
    <path d="${area}" fill="url(#${id})"/><path d="${d}" fill="none" stroke="#a5b4fc" stroke-width="1.6"/></svg>`;
}

function renderSignals(s) {
  const byMetric = Object.fromEntries((s.overview || []).map((m) => [m.metric, m]));
  $("#sec-signals").innerHTML = `<h3><span class="num">3</span>Signals around the incident</h3>
    <p class="sub">Last 20 minutes. Red band = the 10-minute window under analysis; dashed line = alert fired.</p>
    <div class="charts">${s.series
      .map((series) => {
        const m = byMetric[series.metric];
        return `<div class="chart"><div class="ct">${esc(series.metric)}</div>
          <div class="cv"><span>${m ? `${sig(m.baseline_mean)} → ${sig(m.recent_mean)}` : "SLO signal"}</span>${m ? `<span class="z ${zClass(m.z_score)}">z ${fmt(m.z_score, 1)}</span>` : ""}</div>
          ${sparkline(series, s.now)}</div>`;
      })
      .join("")}</div>`;
}

const TOOL_ICON = { get_metrics: "📈", search_logs: "🔎", get_topology: "🕸️" };

function renderAgent(s) {
  const a = s.agent;
  const llm = S.health?.llm_model;
  const calls = a.steps.filter((x) => x.tool).length;
  const running = a.status === "running";
  const started = a.status !== "idle";
  const steps = a.steps
    .map((st) => {
      if (!st.tool) return `<div class="step final"><div class="sh"><span class="tool">final answer</span><span class="lat">${fmt(st.latency_s, 1)}s</span></div>
        <div class="sum">Agent stopped calling tools and returned a structured root-cause report.</div></div>`;
      const args = typeof st.arguments === "string" ? st.arguments : JSON.stringify(st.arguments);
      return `<div class="step ${st.valid === false ? "bad" : ""}"><div class="sh">${TOOL_ICON[st.tool] || "🔧"}<span class="tool">${esc(st.tool)}</span>
        <span class="eid evchip" data-ev="${esc(st.evidence_id)}">${esc(st.evidence_id)}</span>
        ${st.valid === false ? `<span class="badge high">invalid</span>` : ""}<span class="lat">${fmt(st.latency_s, 1)}s</span></div>
        <div class="args">${esc(args)}</div><div class="sum">${esc(st.summary)}</div></div>`;
    })
    .join("");
  $("#sec-agent").innerHTML = `<h3><span class="num">4</span>LLM investigation</h3>
    <p class="sub">Bounded ReAct loop · local open-weight model · 3 read-only tools · max 12 calls. It cannot change the system.</p>
    <div class="agentbar">
      <button class="btn primary" id="run-live" ${!llm || running ? "disabled" : ""} title="${llm ? "" : "Start mlx_lm.server on :8080"}">▶ Run live agent${llm ? ` · ${esc(llm.split("/").pop())}` : ""}</button>
      <button class="btn" id="run-saved" ${running ? "disabled" : ""}>⟲ Replay recorded run</button>
      <span class="spacer"></span>
      <div class="budget"><span>${calls}/12 tool calls</span><span class="cells">${Array.from({ length: 12 }, (_, i) => `<i class="${i < calls ? "on" : ""}"></i>`).join("")}</span></div>
    </div>
    ${started ? `<div class="small muted" style="margin:-4px 0 12px">${a.mode === "live" ? "Live run" : "Recorded run (replayed step by step)"} · ${esc(a.model)}${a.seconds ? ` · finished in ${a.seconds}s` : ""}</div>` : ""}
    ${a.error ? `<div class="banner bad">Agent error: ${esc(a.error)}</div>` : ""}
    <div class="steps">${steps}${running ? `<div class="thinking"><span class="dots"><i></i><i></i><i></i></span>Agent is reasoning and choosing the next tool…</div>` : ""}</div>
    ${!started ? `<div class="banner info">Start the investigation. The agent will query metrics, logs and topology through the Telemetry Access Layer and cite every result as evidence (E1, E2, …).</div>` : ""}`;
  $("#run-live").onclick = () => act("investigate", { mode: "live" });
  $("#run-saved").onclick = () => act("investigate", { mode: "saved" });
  bindEvidence("#sec-agent");
}

function bindEvidence(root) {
  document.querySelectorAll(`${root} [data-ev]`).forEach((el) =>
    el.addEventListener("click", () => {
      const id = el.dataset.ev;
      const ev = S.session.agent.evidence[id];
      $("#drawer-title").textContent = `Evidence ${id}`;
      $("#drawer-body").textContent = ev ? JSON.stringify(ev, null, 2) : "No tool result recorded for this id.";
      $("#drawer").classList.remove("hidden");
    })
  );
}
$("#drawer-close").onclick = () => $("#drawer").classList.add("hidden");

function renderRca(s) {
  const d = s.diagnosis;
  if (!d) {
    $("#sec-rca").innerHTML = `<h3><span class="num">5</span>Root-cause report</h3>
      <p class="sub">Appears when the agent finishes.</p><div class="empty" style="height:240px"><div class="faint">No diagnosis yet</div></div>`;
    return;
  }
  const failed = new Set(s.attempts.filter((a) => a.verification && !a.verification.recovered).map((a) => a.target));
  const valid = d.tool_calls - d.invalid_tool_calls;
  $("#sec-rca").innerHTML = `<h3><span class="num">5</span>Root-cause report</h3>
    <p class="sub">Ranked candidates with the agent's claims. Each claim must cite tool results.</p>
    <div class="checks">
      <div class="check ${d.invalid_tool_calls ? "bad" : "good"}"><div class="v">${valid}/${d.tool_calls}</div><div class="l">valid tool calls</div></div>
      <div class="check ${d.unknown_services.length ? "bad" : "good"}"><div class="v">${d.unknown_services.length}</div><div class="l">invented services</div></div>
      <div class="check ${d.unsupported_claims ? "bad" : "good"}"><div class="v">${d.unsupported_claims}</div><div class="l">claims w/o evidence</div></div>
      <div class="check"><div class="v" style="font-size:15px;padding-top:3px">${esc(d.fault)}</div><div class="l">fault family (from ${esc(d.fault_metric || "–")})</div></div>
    </div>
    ${d.candidates
      .map(
        (c) => `<div class="cand ${c.rank === 1 ? "r1" : ""} ${failed.has(c.service) ? "out" : ""}"><div class="rk">#${c.rank}</div>
        <div><div class="svc">${esc(c.service)}</div><div class="meter"><i style="width:${Math.round(c.confidence * 100)}%"></i></div></div>
        <div class="pct">${Math.round(c.confidence * 100)}%</div></div>`
      )
      .join("")}
    <div class="small faint" style="margin:-2px 0 12px">Confidence here is rank-based (1/rank), not calibrated. Calibrated confidence sets are Phase 1 work.</div>
    ${d.claims
      .map(
        (c) => `<div class="claim"><b>${esc(c.service)}</b> — ${esc(c.claim)}
        ${(c.evidence_refs || []).map((e) => `<span class="evchip" data-ev="${esc(e)}">${esc(e)}</span>`).join("")}</div>`
      )
      .join("")}`;
  bindEvidence("#sec-rca");
}

function riskBadge(r) {
  return `<span class="badge ${esc(r)}">risk ${esc(r)}</span>`;
}

function renderPlan(s) {
  const plan = s.plans[s.plans.length - 1];
  if (!plan) {
    $("#sec-plan").innerHTML = `<h3><span class="num">6</span>Remediation plan</h3>
      <p class="sub">The planner maps the diagnosis to an allowlisted playbook action. It is a lookup table, not a second model.</p>
      <div class="empty" style="height:200px"><div class="faint">Waiting for a diagnosis</div></div>`;
    return;
  }
  const waiting = s.status === "awaiting_approval";
  const params = Object.keys(plan.params || {}).length ? JSON.stringify(plan.params) : "—";
  $("#sec-plan").innerHTML = `<h3><span class="num">6</span>Remediation plan ${s.plans.length > 1 ? `<span class="badge info">re-plan #${s.plans.length}</span>` : ""}</h3>
    <p class="sub">One primary remedy for the top candidate, alternatives for ranks 2–3. Nothing runs without your approval.</p>
    <div class="plan">
      <div class="ptop"><span class="badge neutral">${esc(plan.playbook_id)}</span><span class="action">${esc(plan.action)}</span>
        <span class="muted">→</span><b>deploy/${esc(plan.target_service)}</b>${riskBadge(plan.risk)}</div>
      <dl class="kv">
        <dt>Why</dt><dd>${esc(plan.rationale)}</dd>
        <dt>Fault family</dt><dd>${esc(plan.fault_type)}</dd>
        <dt>Namespace</dt><dd class="mono">${esc(plan.namespace)}</dd>
        <dt>Parameters</dt><dd class="mono">${esc(params)}</dd>
        <dt>Undo</dt><dd>${esc(plan.undo || "—")}</dd>
        <dt>Candidate</dt><dd>rank ${esc(plan.rank)} · confidence ${Math.round(plan.confidence * 100)}% (rank-based)</dd>
      </dl>
      <div class="policy"><span>✓ allowlisted action</span><span>✓ allowlisted namespace</span><span>✓ approval record required</span><span>✓ dry-run executor</span></div>
      ${plan.secondary?.length
        ? `<table class="t" style="margin-top:10px"><tr><th>Alternative</th><th>Service</th><th>Action</th></tr>
          ${plan.secondary.map((x) => `<tr><td>rank ${esc(x.rank)}</td><td>${esc(x.service)}</td><td class="mono">${esc(x.action)}</td></tr>`).join("")}</table>`
        : ""}
    </div>
    <div class="row" style="margin-top:14px">
      <button class="btn go" id="approve-btn" ${waiting ? "" : "disabled"}>✓ Approve &amp; execute</button>
      <button class="btn danger" id="reject-btn" ${waiting ? "" : "disabled"}>✕ Reject</button>
      <span class="spacer"></span>${plan.decision ? `<span class="small muted">Decided by <b>${esc(plan.decision.operator)}</b> · ${esc(plan.decision.decision)}</span>` : ""}
    </div>`;
  $("#approve-btn").onclick = () => openModal("approve", plan);
  $("#reject-btn").onclick = () => openModal("reject", plan);
}

function openModal(kind, plan) {
  const approve = kind === "approve";
  $("#modal-title").textContent = approve ? "Approve remediation" : "Reject remediation";
  $("#modal-sub").innerHTML = `${esc(plan.playbook_id)} · <b>${esc(plan.action)}</b> on deploy/${esc(plan.target_service)} · risk ${esc(plan.risk)}`;
  $("#modal-operator").value = operator();
  $("#modal-note").value = "";
  $("#modal-confirm").checked = false;
  $("#modal-confirm-row").classList.toggle("hidden", !approve);
  $("#modal-ok").className = "btn " + (approve ? "go" : "danger");
  $("#modal-ok").textContent = approve ? "Approve & execute" : "Reject plan";
  $("#modal").classList.remove("hidden");
  $("#modal-ok").onclick = async () => {
    if (approve && !$("#modal-confirm").checked) return toast("Confirm that you reviewed the evidence first.", true);
    if (!$("#modal-operator").value.trim()) return toast("Operator id is required.", true);
    $("#modal").classList.add("hidden");
    await act("decision", { decision: kind, operator: $("#modal-operator").value.trim(), note: $("#modal-note").value });
  };
}
$("#modal-cancel").onclick = () => $("#modal").classList.add("hidden");

function renderExec(s) {
  const last = s.attempts[s.attempts.length - 1];
  const attempts = s.attempts
    .map((a, i) => {
      const ok = a.approval.decision === "approve";
      const v = a.verification;
      return `<div class="attempt"><div class="ah"><b>Attempt ${i + 1}</b><span class="mono small">${esc(a.action)} → ${esc(a.target)}</span>
        <span class="badge ${ok ? "ok" : "high"}">${ok ? "approved" : "rejected"}</span>
        ${v ? `<span class="badge ${v.recovered ? "ok" : "high"}">${v.recovered ? "recovered" : "still failing"}</span>` : ""}</div>
        <div class="terminal"><span class="p">$ approval</span> ${esc(a.approval.id)} by ${esc(a.approval.operator)}${a.approval.note ? ` — "${esc(a.approval.note)}"` : ""}
<span class="p">$ executor</span> status=${esc(a.execution.status)} dry_run=${esc(a.execution.dry_run)}
<span class="${a.execution.status === "rejected" ? "e" : ""}">${esc(a.execution.detail)}</span>${v ? `\n<span class="p">$ verify</span> <span class="${v.recovered ? "" : "w"}">${v.recovered ? "SLO back to baseline" : "SLO still red → feedback loop"}</span> (${esc(v.method)})` : ""}</div></div>`;
    })
    .join("");
  let controls = "";
  if (s.status === "verifying")
    controls = `<div class="banner info">Remedy executed (dry-run). Did the service recover?</div>
      <div class="row" style="margin-top:10px">
        <button class="btn primary" id="v-sim">Check recovery (simulated)</button>
        <button class="btn" id="v-ok">Operator: recovered</button>
        <button class="btn danger" id="v-bad">Operator: still failing → next candidate</button></div>
      <div class="small faint" style="margin-top:8px">Simulated check: in replay the fix cannot really run, so recovery is decided by the benchmark label. In 295B this is a live SLO query.</div>`;
  else if (s.status === "rejected")
    controls = `<div class="banner bad">Plan rejected — nothing was executed.</div>
      <div class="row" style="margin-top:10px"><button class="btn primary" id="v-next">Propose remedy for the next candidate</button></div>`;
  else if (s.status === "resolved")
    controls = `<div class="banner good">✓ Incident resolved after ${s.attempts.filter((a) => a.approval.decision === "approve").length} approved remedy attempt(s).</div>`;
  else if (s.status === "escalated")
    controls = `<div class="banner bad">Escalated to the on-call engineer: the playbook has no safe automatic action left (PB-05 / PB-10). The copilot never invents actions.</div>`;
  $("#sec-exec").innerHTML = `<h3><span class="num">7</span>Execute &amp; verify</h3>
    <p class="sub">Allowlisted executor in dry-run mode. A failed remedy feeds back to the planner, which needs a fresh approval.</p>
    ${attempts || `<div class="empty" style="height:160px"><div class="faint">Nothing executed yet — approval required</div></div>`}${controls}`;
  const bind = (id, fn) => { const el = $(id); if (el) el.onclick = fn; };
  bind("#v-sim", () => act("verify", { outcome: "simulate", operator: operator() }));
  bind("#v-ok", () => act("verify", { outcome: "recovered", operator: operator() }));
  bind("#v-bad", () => act("verify", { outcome: "not_recovered", operator: operator() }));
  bind("#v-next", () => act("replan", { operator: operator() }));
  void last;
}

function renderAudit(s) {
  $("#sec-audit").innerHTML = `<h3><span class="num">8</span>Audit trail</h3>
    <p class="sub">Append-only record of every automated step and human decision.</p>
    <div class="audit">${s.audit
      .slice()
      .reverse()
      .map((e) => `<div class="aud"><span class="at">${esc(e.at.slice(11, 19))}</span><span class="who">${esc(e.actor)}</span><span>${esc(e.text)}</span></div>`)
      .join("")}</div>`;
}

function renderReveal(s) {
  const r = s.revealed;
  if (!r) {
    $("#sec-reveal").innerHTML = `<h3><span class="num">9</span>Check against ground truth</h3>
      <p class="sub">For the demo only: the benchmark label and the official baselines' answers, hidden from the agent.</p>
      <button class="btn" id="reveal-btn">👁 Reveal ground truth</button>`;
    $("#reveal-btn").onclick = () => act("reveal");
    return;
  }
  const rank = (list) => {
    const i = list.indexOf(r.service);
    return i < 0 ? "not in top-5" : `rank ${i + 1}`;
  };
  const agentTop = s.diagnosis?.top_services || [];
  const rows = [["LLM agent (this run)", agentTop], ...Object.entries(r.baselines)];
  $("#sec-reveal").innerHTML = `<h3><span class="num">9</span>Check against ground truth</h3>
    <div class="banner ${r.agent_rank === 1 ? "good" : "bad"}" style="margin-top:4px">True root cause: <span class="mono">${esc(r.service)}</span> · fault <span class="mono">${esc(r.fault)}</span>
      — agent ${r.agent_rank ? `ranked it #${r.agent_rank}` : "missed it"}</div>
    <table class="t" style="margin-top:12px"><tr><th>Method</th><th>Top-3</th><th>Truth</th></tr>
    ${rows
      .map(([name, list]) => `<tr class="${list[0] === r.service ? "hl" : ""}"><td>${esc(name)}</td><td class="mono small">${esc(list.slice(0, 3).join(" › "))}</td><td>${rank(list)}</td></tr>`)
      .join("")}</table>
    <div class="small faint" style="margin-top:8px">Baselines: official RCAEval main.py runs (N1).</div>`;
}

/* ---------- evaluation page ---------- */
function md(text) {
  const lines = text.split("\n");
  let html = "", inList = false, table = [];
  const inline = (t) => esc(t).replace(/\*\*(.+?)\*\*/g, "<b>$1</b>").replace(/`(.+?)`/g, "<code>$1</code>").replace(/\*(.+?)\*/g, "<i>$1</i>");
  const flushTable = () => {
    if (!table.length) return;
    const rows = table.filter((r) => !/^\|[-|: ]+\|$/.test(r));
    html += "<table>" + rows.map((r, i) => "<tr>" + r.split("|").slice(1, -1).map((c) => (i ? `<td>${inline(c.trim())}</td>` : `<th>${inline(c.trim())}</th>`)).join("") + "</tr>").join("") + "</table>";
    table = [];
  };
  let para = [];
  const flushPara = () => { if (para.length) { html += `<p>${inline(para.join(" "))}</p>`; para = []; } };
  for (const raw of lines) {
    const line = raw.trimEnd();
    if (line.startsWith("|")) { flushPara(); table.push(line); continue; }
    flushTable();
    if (/^#{1,3} /.test(line)) { flushPara(); if (inList) { html += "</ul>"; inList = false; } const n = line.match(/^#+/)[0].length; html += `<h${n}>${inline(line.slice(n + 1))}</h${n}>`; }
    else if (/^\s*- /.test(line)) { flushPara(); if (!inList) { html += "<ul>"; inList = true; } html += `<li>${inline(line.replace(/^\s*- /, ""))}</li>`; }
    else if (/^\s{2,}\S/.test(line) && inList) { html = html.replace(/<\/li>$/, " " + inline(line.trim()) + "</li>"); }
    else if (!line.trim()) { flushPara(); if (inList) { html += "</ul>"; inList = false; } }
    else para.push(line);
  }
  flushPara(); flushTable(); if (inList) html += "</ul>";
  return html;
}

function barRows(rows) {
  return `<div class="bars">${rows
    .map(
      (r) => `<div class="brow"><span>${esc(r.label)}${r.note ? ` <span class="faint small">${esc(r.note)}</span>` : ""}</span>
      <div class="track"><div class="fill ${r.kind || ""}" style="width:calc(${r.v * 100}% - 4px)"></div>
        ${r.lo !== undefined ? `<div class="ci" style="left:${r.lo * 100}%;width:${(r.hi - r.lo) * 100}%"></div>` : ""}</div>
      <span class="val">${fmt(r.v)}${r.lo !== undefined ? ` [${fmt(r.lo)}, ${fmt(r.hi)}]` : ""}</span></div>`
    )
    .join("")}</div>`;
}

async function renderEval() {
  if (!S.evalData) S.evalData = await api("/api/evaluation");
  const { n1, runs, failure_modes } = S.evalData;
  const methods = Object.entries(n1.methods || {});
  const official = methods.filter(([, m]) => !m.source.includes("diagnostic"));
  const sub = n1.agent_subset || {};
  const subTables = sub.tables || {};
  const ext = runs.find((r) => r.run.startsWith("extended30")) || {};
  const best = official.filter(([k]) => k !== "dummy").sort((a, b) => b[1].table.all["AC@1"] - a[1].table.all["AC@1"])[0];
  const ac = (t) => t.all["AC@1"];
  $("#eval").innerHTML = `
    <h1>Preliminary evaluation</h1>
    <p class="lede">Evidence that the pipeline works as conceived, on the public RCAEval RE2-OB benchmark (Online Boutique, 90 labelled faults: CPU, memory, disk, socket, delay, packet loss). All numbers use the oracle onset clock; detected onset is the next re-run.</p>
    <div class="kpis">
      <div class="kpi"><div class="v" style="color:var(--green)">${fmt(subTables.agent?.all?.["AC@1"])}</div><div class="l">LLM agent AC@1</div><div class="n">${sub.n_cases || 30} cases, Qwen3-4B on a laptop</div></div>
      <div class="kpi"><div class="v">${best ? fmt(ac(best[1].table)) : "–"}</div><div class="l">Best official baseline AC@1</div><div class="n">${best ? esc(best[1].label) : ""}, 90 cases</div></div>
      <div class="kpi"><div class="v">${ext.valid_tool_call_rate !== undefined ? Math.round(ext.valid_tool_call_rate * 100) + "%" : "–"}</div><div class="l">Valid tool calls</div><div class="n">no invented metrics, no loops</div></div>
      <div class="kpi"><div class="v">${ext.mean_seconds_per_case ?? "–"}s</div><div class="l">Mean investigation time</div><div class="n">per incident, Apple Silicon</div></div>
    </div>

    <h2>Correlation / ranking baselines (N1) — AC@1 with 95% CI, 90 cases</h2>
    <div class="card">${barRows(
      methods.map(([k, m]) => ({
        label: m.label, note: m.source.includes("diagnostic") ? "diagnostic" : "",
        v: m.table.all["AC@1"], lo: m.table.all["AC@1_lo"], hi: m.table.all["AC@1_hi"],
        kind: m.source.includes("diagnostic") ? "diag" : "",
      }))
    )}
    <table class="t" style="margin-top:16px"><tr><th>Method</th><th>Source</th><th>AC@1</th><th>AC@3</th><th>AC@5</th><th>Avg@5</th></tr>
      ${methods.map(([, m]) => `<tr class="${m.source.includes("diagnostic") ? "dim" : ""}"><td>${esc(m.label)}</td><td class="small muted">${esc(m.source)}</td>
        ${["AC@1", "AC@3", "AC@5", "Avg@5"].map((k) => `<td class="mono">${fmt(m.table.all[k])}</td>`).join("")}</tr>`).join("")}</table>
    <p class="small muted" style="margin-top:12px">Official rows: unmodified RCAEval <code>main.py</code> at a pinned commit; our scorer reproduces its printed Avg@5 exactly. Our earlier "BARO 0.30" came from calling BARO without its dataset argument; BARO's redis bias comes from a zero-variance metric (<code>redis_diskio</code>) and disappears with a zero-IQR guard (0.81, diagnostic).</p></div>

    <h2>AI engine (N3) vs baselines on the same ${sub.n_cases || 30} incidents</h2>
    <div class="card">${barRows(
      Object.entries(subTables).map(([k, t]) => ({
        label: k === "agent" ? "LLM agent (Qwen3-4B)" : n1.methods[k]?.label || k,
        v: t.all["AC@1"], lo: t.all["AC@1_lo"], hi: t.all["AC@1_hi"], kind: k === "agent" ? "agent" : "",
      }))
    )}
    <p class="small muted" style="margin-top:10px">Paired bootstrap, agent − baseline AC@1: ${Object.entries(sub.paired_bootstrap || {})
      .filter(([k]) => k.endsWith("AC@1"))
      .map(([k, v]) => `${esc(n1.methods[k.split("_")[2]]?.label || k)} <b>${v.diff >= 0 ? "+" : ""}${fmt(v.diff)}</b> [${fmt(v.ci[0])}, ${fmt(v.ci[1])}]`)
      .join(" · ")}. The lead over N-Sigma is not significant yet.</p></div>

    <h2>Agent runs</h2>
    <div class="card"><table class="t"><tr><th>Run</th><th>Model</th><th>Prompt</th><th>Cases</th><th>AC@1</th><th>AC@3</th><th>Valid calls</th><th>s / case</th></tr>
      ${runs.map((r) => `<tr><td class="mono small">${esc(r.run)}</td><td>${esc(r.model)}</td><td>${esc(r.prompt)}</td><td>${r.n_cases}</td><td class="mono">${fmt(r.ac1)}</td><td class="mono">${fmt(r.ac3)}</td><td class="mono">${Math.round(r.valid_tool_call_rate * 100)}%</td><td class="mono">${r.mean_seconds_per_case}</td></tr>`).join("")}</table></div>

    ${plannerSection(S.evalData.planner)}

    <h2>Failure modes observed</h2>
    <div class="card md">${md(failure_modes.replace(/^# .*\n/, ""))}</div>`;
}

function plannerSection(p) {
  if (!p) return "";
  const fc = p.fault_classification_90;
  const a = p.planner_30_max.summary;
  const b = p.planner_30_resource_first.summary;
  const faults = Object.keys(fc.max.by_fault);
  const pct = (x) => `${Math.round(x * 100)}%`;
  const row = (label, key, f = pct) => `<tr><td>${label}</td><td class="mono">${f(a[key])}</td><td class="mono">${f(b[key])}</td></tr>`;
  return `
    <h2>Planner (top-k → remedy → feedback loop) on the same 30 incidents</h2>
    <p class="sub">Agent ranking → fault family from the cited metrics → playbook entry → approval. A failed verification rules the service out and the planner proposes the next candidate. "Resolved" here means the remedy targeted the true service (benchmark label); the remedy type is scored separately.</p>
    <div class="grid g2">
      <div class="card"><table class="t"><tr><th>Metric</th><th>Most-changed metric</th><th>Resource-first rule</th></tr>
        ${row("First plan targets the true service", "first_plan_target_correct")}
        ${row("Fault family correct", "fault_hint_correct")}
        ${row("First plan fully correct (service + playbook)", "fully_correct_first_plan")}
        <tr><td>Resolved within 1 / 2 / 3 approvals</td><td class="mono" colspan="2">${[1, 2, 3].map((k) => pct(b.resolved_within_k_approvals[k])).join(" / ")}</td></tr>
        ${row("Mean approvals when resolved", "mean_approvals_when_resolved", (x) => x.toFixed(2))}
        ${row("Wrong-target write proposals / incident", "wrong_target_write_proposals_per_incident", (x) => x.toFixed(2))}
      </table></div>
      <div class="card"><h3>Fault-family classification, all ${fc.n_cases} cases</h3><p class="sub">True service given, so this isolates the classification step. Latency rises under every fault, so the resource-first rule prefers a CPU / memory / disk / socket change beyond 3σ.</p>
        <table class="t"><tr><th>Fault</th><th>Most-changed</th><th>Resource-first</th></tr>
        ${faults.map((f) => `<tr><td>${f}</td><td class="mono">${pct(fc.max.by_fault[f])}</td><td class="mono">${pct(fc.resource_first.by_fault[f])}</td></tr>`).join("")}
        <tr><td><b>all</b></td><td class="mono"><b>${pct(fc.max.accuracy)}</b></td><td class="mono"><b>${pct(fc.resource_first.accuracy)}</b></td></tr></table>
        <p class="sub">Packet loss is indistinguishable from delay in these metrics (0%); the planner needs network-error signals or escalation for it.</p></div>
    </div>`;
}

/* ---------- architecture page ---------- */
function renderArch() {
  $("#arch").innerHTML = `
    <h1>Architecture and processing flow</h1>
    <p class="lede">Two separate artifacts: the <b>system architecture</b> is what exists (components, interfaces, owners); the <b>processing flow</b> is what happens over time, including the failure and feedback paths.</p>
    <div class="grid g2">
      <div class="card"><h3>System architecture</h3><p class="sub">Static components and boundaries.</p><div class="figure"><img src="/figures/system_architecture.png" alt="System architecture" onerror="this.parentElement.innerHTML='<p style=color:#333>Figure not found</p>'"/></div></div>
      <div class="card"><h3>Processing flow</h3><p class="sub">Runtime sequence with the feedback loop.</p><div class="figure"><img src="/figures/processing_flow.png" alt="Processing flow" onerror="this.parentElement.innerHTML='<p style=color:#333>Figure not found</p>'"/></div></div>
    </div>
    <h2>Runtime pipeline in this prototype</h2>
    <div class="pipeline">
      <div class="pn"><b>Telemetry Access Layer</b><span>Read-only; Prometheus-shaped metrics, logs, traces, topology; clock-clipped</span></div><span class="arrow">→</span>
      <div class="pn"><b>AI engine</b><span>Qwen3-4B, bounded ReAct, 3 tools, ≤12 calls, cited evidence</span></div><span class="arrow">→</span>
      <div class="pn"><b>Planner</b><span>Playbook lookup: top-1 → primary remedy; ranks 2–3 → alternatives</span></div><span class="arrow">→</span>
      <div class="pn"><b>Approval gate</b><span>Operator id + reason, append-only audit</span></div><span class="arrow">→</span>
      <div class="pn"><b>Executor</b><span>Allowlisted actions and namespaces, dry-run</span></div><span class="arrow">→</span>
      <div class="pn"><b>Verifier</b><span>SLO check; failure → next candidate, re-approval</span></div>
    </div>
    <h2>Answers to the flow questions</h2>
    <div class="qa">
      <div class="card"><h3>One remedy or several?</h3><p>One <b>primary</b> remedy for the top-ranked candidate, plus <b>alternatives</b> for ranks 2–3 shown side by side. The operator approves one at a time; every remedy comes from the allowlisted playbook — the planner never invents actions.</p></div>
      <div class="card"><h3>From top-k with confidence to remedies</h3><p>The agent returns ranked services with cited evidence. The fault family comes from the evidence (the top service's most-changed metric: cpu, mem, disk, socket, latency). The planner looks up <code>(fault family, service)</code> in the playbook → action, parameters, risk, undo. Low-confidence or unknown faults map to escalation (PB-10).</p></div>
      <div class="card"><h3>What if the remedy doesn't work?</h3><p>Verification fails → the service is ruled out → the planner drafts the next candidate's remedy → a <b>new approval</b> is required. When the top-k is exhausted, or the fault is outside app control (packet loss), the copilot escalates to a human. Try it in the console: reject a plan or mark "still failing".</p></div>
      <div class="card"><h3>Why is diagnosis safe to automate?</h3><p>The AI engine has only read tools behind the Telemetry Access Layer. Writes exist only in the executor, which refuses anything without an approval record, outside the allowlist, or outside allowed namespaces.</p></div>
    </div>`;
}

function renderAbout() {
  $("#about").innerHTML = `
    <h1>Team contributions &amp; safety properties</h1>
    <p class="lede">One end-to-end path through every member's components.</p>
    <div class="team">
      <div class="card"><h3>Charan Sai Gandham</h3><ul><li>Kind / Online Boutique / Chaos Mesh testbed</li><li>Telemetry gateway and event schema</li><li>Fault scenarios and onset detection (C1–C3)</li></ul></div>
      <div class="card"><h3>Naga Charan Patrini</h3><ul><li>N1: official RCAEval baselines with CIs; BARO 0.30 gap explained</li><li>N2: Telemetry Access Layer + leakage-tested replay</li><li>N3: local LLM agent, tools, bounded ReAct, trajectories</li></ul></div>
      <div class="card"><h3>Vishnu Sree Peram</h3><ul><li>Remediation playbook planner</li><li>Approval gate and audit log</li><li>Allowlisted executor; evaluation interface</li></ul></div>
    </div>
    <h2>Safety properties demonstrated</h2>
    <div class="qa">
      <div class="card"><ul><li>Diagnosis path is read-only (no write tools exist in the agent).</li><li>No execution without an approval record with operator id.</li><li>Executor rejects off-allowlist actions and namespaces.</li><li>Default mode is dry-run; nothing touches a cluster.</li></ul></div>
      <div class="card"><ul><li>A failed remedy loops back to planning and needs a fresh approval.</li><li>The agent sees an anonymous case id and no data after <i>now</i> (leakage tests).</li><li>Every claim cites tool evidence ids; invalid tool calls are counted, not hidden.</li><li>Honest limits: oracle onset clock, rank-based confidence, 30-case sample.</li></ul></div>
    </div>`;
}

/* ---------- boot ---------- */
(async function boot() {
  await refreshHealth();
  await loadQueue();
  setInterval(refreshHealth, 15000);
})();
