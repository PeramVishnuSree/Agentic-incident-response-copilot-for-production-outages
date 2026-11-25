"use strict";

/* Server-free replay mode: the /api/* endpoints of console/web_app.py, run in the
   browser on data precomputed by scripts/build_static_site.py. Sessions live in
   this browser's localStorage, so every visitor has their own incidents. */
(() => {
  const STEP_MS = 900;
  const STORE = "copilot-static-sessions-v1";
  const cases = {};
  let labels = null;
  let evaluation = null;

  const load = () => JSON.parse(localStorage.getItem(STORE) || "{}");
  const save = (all) => localStorage.setItem(STORE, JSON.stringify(all));
  const json = (url) => fetch(url).then((r) => {
    if (!r.ok) throw new Error(`${url}: ${r.statusText}`);
    return r.json();
  });
  const rid = (prefix) => `${prefix}-${Math.random().toString(16).slice(2, 12).padEnd(10, "0")}`;
  const nowIso = () => new Date().toISOString();
  const fail = (msg) => { throw new Error(msg); };

  async function caseData(index) {
    if (!cases[index]) cases[index] = await json(`data/case_${index}.json`);
    return cases[index];
  }

  async function caseLabels() {
    if (!labels) labels = (await json("data/index.json")).labels;
    return labels;
  }

  const log = (s, actor, kind, text) => s.audit.push({ at: nowIso(), actor, kind, text });

  function fresh(c) {
    const s = { id: rid("s"), index: c.index, status: "detected", audit: [], agent: idleAgent(), plans: [], attempts: [], revealed: null };
    c.open_audit.forEach(([actor, kind, text]) => log(s, actor, kind, text));
    return s;
  }

  function idleAgent() {
    return { status: "idle", mode: null, model: null, started: null, seconds: null, error: null, diagnosed: false };
  }

  function propose(s, c) {
    const link = c.chain[Math.min(s.plans.length, c.chain.length - 1)];
    s.plans.push({ ...link.plan, id: rid("plan"), decision: null, link: c.chain.indexOf(link) });
    s.status = "awaiting_approval";
    log(s, "planner", "plan", link.log);
  }

  function advance(s, c) {
    const a = s.agent;
    if (a.status !== "running") return;
    const shown = Math.floor((Date.now() - a.started) / STEP_MS);
    if (shown < c.steps.length) return;
    a.status = "done";
    a.seconds = Math.round((Date.now() - a.started) / 100) / 10;
    a.diagnosed = true;
    log(s, "agent", "diagnosis", c.diagnosis_log);
    if (!c.chain.length) {
      s.status = "escalated";
      log(s, "planner", "escalate", "No candidates: escalate to on-call (PB-10)");
      return;
    }
    propose(s, c);
  }

  function view(s, c) {
    const a = s.agent;
    const running = a.status === "running";
    const shown = running ? Math.min(c.steps.length, Math.floor((Date.now() - a.started) / STEP_MS)) : a.status === "idle" ? 0 : c.steps.length;
    const steps = c.steps.slice(0, shown);
    const evidence = {};
    steps.forEach((st) => { if (st.evidence_id && c.evidence[st.evidence_id]) evidence[st.evidence_id] = c.evidence[st.evidence_id]; });
    return {
      id: s.id,
      label: c.label,
      case_id: c.case_id,
      now: c.now,
      clock_source: c.clock_source,
      status: s.status,
      ...c.opened,
      agent: { status: a.status, mode: a.mode, model: a.model, steps, evidence, error: a.error, started: a.started && a.started / 1000, seconds: a.seconds, budget: 12 },
      diagnosis: a.diagnosed ? c.diagnosis : null,
      plans: s.plans.map(({ link, ...p }) => p),
      attempts: s.attempts,
      audit: s.audit,
      revealed: s.revealed,
    };
  }

  function replan(s, c) {
    if (!["rejected", "verifying"].includes(s.status) || !s.plans.length) fail("nothing to re-plan");
    propose(s, c);
  }

  const handlers = {
    decision(s, c, body) {
      if (s.status !== "awaiting_approval" || !s.plans.length) fail("no plan is awaiting approval");
      const operator = (body.operator || "").trim();
      if (!operator) fail("operator id is required");
      const plan = s.plans[s.plans.length - 1];
      const approve = body.decision === "approve";
      const record = { id: rid("appr"), plan_id: plan.id, decision: approve ? "approve" : "reject", operator, decided_at: nowIso(), note: body.note || "", edited_action: null };
      const link = c.chain[plan.link];
      const execution = { ...(approve ? link.approve : link.reject), id: rid("exec"), plan_id: plan.id, approval_id: approve ? record.id : null, executed_at: nowIso() };
      plan.decision = record;
      s.attempts.push({ plan_id: plan.id, target: plan.target_service, action: plan.action, approval: record, execution, verification: null });
      log(s, operator, approve ? "approval" : "rejection", `${approve ? "Approved" : "Rejected"} ${plan.action} on ${plan.target_service}${body.note ? `: ${body.note}` : ""}`);
      log(s, "executor", "execute", execution.detail);
      s.status = !approve ? "rejected" : plan.action === "escalate_manual" ? "escalated" : "verifying";
    },
    replan,
    verify(s, c, body) {
      if (s.status !== "verifying" || !s.attempts.length) fail("no executed remedy to verify");
      const plan = s.plans[s.plans.length - 1];
      const simulate = (body.outcome || "simulate") === "simulate";
      const recovered = simulate ? plan.target_service === c.truth_service : body.outcome === "recovered";
      const method = simulate ? "simulated from the benchmark label (replay only; live SLO check in 295B)" : `reported by ${body.operator || "operator"}`;
      s.attempts[s.attempts.length - 1].verification = { recovered, method };
      log(s, "verifier", "verify", `${recovered ? "SLO recovered" : "Still failing"} after ${plan.action} on ${plan.target_service} (${method})`);
      if (recovered) s.status = "resolved";
      else replan(s, c);
    },
    reveal(s, c) {
      s.revealed = c.revealed;
      log(s, "operator", "reveal", `Ground truth revealed: ${c.revealed.service} (${c.revealed.fault})`);
    },
    investigate(s, c, body) {
      if (s.agent.status === "running") fail("investigation already running");
      if ((body.mode || "live") === "live") fail("No LLM in the hosted demo; use the recorded run");
      s.agent = { ...idleAgent(), status: "running", mode: "saved", model: c.model, started: Date.now() };
      s.plans = [];
      s.attempts = [];
      s.status = "investigating";
      log(s, "agent", "start", `Investigation started (saved, ${c.model})`);
    },
  };

  async function sessionById(all, sid) {
    const s = Object.values(all).find((x) => x.id === sid) || fail("unknown session");
    return [s, await caseData(s.index)];
  }

  window.staticApi = async (path, body) => {
    const all = load();
    let m;
    if (path === "/api/health") return { llm_model: null, llm_url: null, cases: (await caseLabels()).length, hosted: true };
    if (path === "/api/evaluation") return evaluation || (evaluation = await json("data/evaluation.json"));
    if (path === "/api/incidents") {
      for (const s of Object.values(all)) if (s.agent.status === "running") advance(s, await caseData(s.index));
      save(all);
      return (await caseLabels()).map((label, index) => ({ index, label, session: all[index]?.id ?? null, status: all[index]?.status ?? "new" }));
    }
    if ((m = path.match(/^\/api\/incidents\/(\d+)\/(open|reset)$/))) {
      const index = +m[1];
      if (index < 0 || index >= (await caseLabels()).length) fail("unknown incident");
      const c = await caseData(index);
      if (m[2] === "reset" || !all[index]) all[index] = fresh(c);
      advance(all[index], c);
      save(all);
      return view(all[index], c);
    }
    if ((m = path.match(/^\/api\/sessions\/([^/]+)(?:\/(\w+))?$/))) {
      const [s, c] = await sessionById(all, m[1]);
      advance(s, c);
      if (m[2]) (handlers[m[2]] || fail("unknown action"))(s, c, body || {});
      save(all);
      return view(s, c);
    }
    fail(`unknown endpoint ${path}`);
  };
})();
