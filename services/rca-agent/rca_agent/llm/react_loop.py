"""Bounded ReAct investigation over the read-only Telemetry Access Layer."""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from typing import Any

from rca_agent.tools.telemetry import dispatch, schemas

SYSTEM_PROMPT = """You are an SRE assistant diagnosing a microservice incident.
Rules:
- You may only read telemetry through the tools. You cannot change the system.
- Times are unix seconds. The current time is now={now}. An alert fired a few minutes
  before now, so compare the most recent minutes against the period before them.
- Every tool result has an id like "E1". Cite those ids as evidence.
- You have at most {budget} tool calls. Stop calling tools once you are confident.
When finished, reply with ONLY a JSON object, no prose:
{{"top_services": ["most likely root-cause service", "second", "third"],
  "claims": [{{"service": "...", "claim": "what is abnormal and why it is the cause",
              "evidence_refs": ["E1"]}}]}}
Services must come from this list: {services}.{strategy}"""

STRATEGIES = {
    "v1": "",
    "v2": """
Suggested procedure:
1. get_metrics with no service and start=-600, end=0 to see which metrics changed most.
2. For the 2-3 services whose own metrics (cpu, mem, diskio, socket, latency, error) changed
   most, call get_metrics with that service, and search_logs for errors or timeouts.
3. Use get_topology to separate the cause from callers that only slow down because a
   dependency is slow: the root cause is usually the furthest downstream abnormal service.
4. Rank services by how directly their own resource or latency metrics changed.""",
}

USER_PROMPT = "Investigate incident {case_id}. Find the root-cause service."
REPAIR_PROMPT = (
    "Reply now with ONLY the final JSON object "
    '{"top_services": [...], "claims": [...]} and no other text.'
)
_THINK = re.compile(r"<think>.*?</think>", re.DOTALL)
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


@dataclass
class Step:
    turn: int
    latency_s: float
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    tool: str | None = None
    arguments: Any = None
    valid: bool | None = None
    error: str | None = None
    evidence_id: str | None = None


@dataclass
class Trajectory:
    case_id: str
    now: int
    prompt: str = "v2"
    status: str = "running"
    top_services: list[str] = field(default_factory=list)
    claims: list[dict] = field(default_factory=list)
    tool_calls: int = 0
    invalid_tool_calls: int = 0
    unknown_services: list[str] = field(default_factory=list)
    unsupported_claims: int = 0
    parse_repairs: int = 0
    steps: list[dict] = field(default_factory=list)
    messages: list[dict] = field(default_factory=list)

    def as_dict(self) -> dict:
        return asdict(self)


def parse_answer(content: str | None) -> dict | None:
    """Extract the final JSON object from a model reply (tolerates think tags and fences)."""
    if not content:
        return None
    text = _THINK.sub("", content).strip()
    fenced = _FENCE.search(text)
    if fenced:
        text = fenced.group(1).strip()
    start = text.find("{")
    while start != -1:
        depth = 0
        for index in range(start, len(text)):
            if text[index] == "{":
                depth += 1
            elif text[index] == "}":
                depth -= 1
                if depth == 0:
                    try:
                        value = json.loads(text[start : index + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(value, dict) and "top_services" in value:
                        return value
                    break
        start = text.find("{", start + 1)
    return None


def _clean(message: dict) -> dict:
    kept = {"role": message.get("role", "assistant"), "content": message.get("content") or ""}
    if message.get("tool_calls"):
        kept["tool_calls"] = message["tool_calls"]
    return kept


def _finish(trajectory: Trajectory, answer: dict, services: list[str], evidence: set[str]) -> None:
    tops = [str(s) for s in answer.get("top_services", []) if s]
    claims = [c for c in answer.get("claims", []) if isinstance(c, dict)]
    trajectory.top_services = tops[:5]
    trajectory.claims = claims
    trajectory.unknown_services = [s for s in tops if services and s not in services]
    trajectory.unsupported_claims = sum(
        1
        for c in claims
        if not c.get("evidence_refs") or not set(map(str, c["evidence_refs"])) <= evidence
    )


def run_react(
    llm: Any,
    source: Any,
    *,
    case_id: str,
    max_tool_calls: int = 12,
    max_tokens: int = 1024,
    no_think: bool = True,
    prompt: str = "v2",
    on_step: Callable[[dict, Any], None] | None = None,
) -> dict:
    """Run the loop; ``on_step(step, tool_result)`` is called after every model turn."""
    notify = on_step or (lambda step, result: None)
    services = list(source.topology().get("services", []))
    trajectory = Trajectory(case_id=case_id, now=int(source.now()), prompt=prompt)
    user = USER_PROMPT.format(case_id=case_id) + (" /no_think" if no_think else "")
    messages: list[dict] = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT.format(
                now=trajectory.now,
                budget=max_tool_calls,
                services=", ".join(services),
                strategy=STRATEGIES[prompt],
            ),
        },
        {"role": "user", "content": user},
    ]
    evidence: set[str] = set()
    repaired = False
    turn = 0
    while True:
        turn += 1
        started = time.perf_counter()
        response = llm.chat(messages, tools=schemas(), max_tokens=max_tokens)
        usage = response.get("usage") or {}
        message = (response.get("choices") or [{}])[0].get("message", {})
        messages.append(_clean(message))
        base = {
            "turn": turn,
            "latency_s": round(time.perf_counter() - started, 2),
            "prompt_tokens": usage.get("prompt_tokens"),
            "completion_tokens": usage.get("completion_tokens"),
        }
        calls = message.get("tool_calls") or []
        if not calls:
            trajectory.steps.append(asdict(Step(**base)))
            notify(trajectory.steps[-1], None)
            answer = parse_answer(message.get("content"))
            if answer is not None:
                _finish(trajectory, answer, services, evidence)
                trajectory.status = "completed"
                break
            if repaired:
                trajectory.status = "unparseable_answer"
                break
            repaired = True
            trajectory.parse_repairs += 1
            messages.append({"role": "user", "content": REPAIR_PROMPT})
            continue
        exhausted = False
        for call in calls:
            if trajectory.tool_calls >= max_tool_calls:
                exhausted = True
                break
            function = call.get("function", {})
            name = function.get("name", "")
            raw = function.get("arguments", "{}")
            trajectory.tool_calls += 1
            evidence_id = f"E{trajectory.tool_calls}"
            step = Step(**base, tool=name, arguments=raw, evidence_id=evidence_id)
            try:
                arguments = json.loads(raw) if isinstance(raw, str) else dict(raw or {})
                step.arguments = arguments
                result = {"id": evidence_id, **dispatch(source, name, arguments)}
                step.valid = True
                evidence.add(evidence_id)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
                trajectory.invalid_tool_calls += 1
                step.valid, step.error = False, str(exc)
                result = {"id": evidence_id, "error": str(exc)}
            trajectory.steps.append(asdict(step))
            notify(trajectory.steps[-1], result)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": call.get("id", evidence_id),
                    "name": name,
                    "content": json.dumps(result, default=str)[:6000],
                }
            )
        if exhausted or trajectory.tool_calls >= max_tool_calls:
            messages.append({"role": "user", "content": "Tool budget used up. " + REPAIR_PROMPT})
            response = llm.chat(messages, max_tokens=max_tokens)
            message = (response.get("choices") or [{}])[0].get("message", {})
            messages.append(_clean(message))
            answer = parse_answer(message.get("content"))
            if answer is not None:
                _finish(trajectory, answer, services, evidence)
            trajectory.status = "tool_budget_exhausted"
            break
    trajectory.messages = messages
    return trajectory.as_dict()
