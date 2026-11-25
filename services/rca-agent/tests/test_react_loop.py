import json

from rca_agent.llm.react_loop import parse_answer, run_react
from rca_agent.tools.telemetry import dispatch

NOW = 1_000


class Source:
    def now(self):
        return NOW

    def metrics(self, service, start, end, step=1):
        times = range(start, min(end, NOW) + 1)
        series = {
            "checkoutservice_cpu": [50.0 if t > NOW - 60 else 1.0 + (t % 3) * 0.1 for t in times],
            "frontend_cpu": [2.0 + (t % 2) * 0.1 for t in times],
        }
        result = [
            {
                "metric": {"__name__": name},
                "values": [[t, str(v)] for t, v in zip(times, vals, strict=True)],
            }
            for name, vals in series.items()
            if service is None or name.startswith(service)
        ]
        return {"data": {"resultType": "matrix", "result": result}}

    def logs(self, service, start, end, pattern=None, limit=100):
        rows = [
            {"timestamp": t, "service": "checkoutservice", "message": "error 42"}
            for t in range(max(start, NOW - 30), min(end, NOW) + 1)
        ]
        return rows[:limit]

    def topology(self):
        return {
            "services": ["checkoutservice", "frontend"],
            "edges": [{"caller": "frontend", "callee": "checkoutservice", "calls": 9}],
        }


def _tool_call(name, arguments):
    return {
        "choices": [
            {
                "message": {
                    "role": "assistant",
                    "content": "",
                    "tool_calls": [
                        {"id": "1", "function": {"name": name, "arguments": json.dumps(arguments)}}
                    ],
                }
            }
        ],
        "usage": {"prompt_tokens": 10, "completion_tokens": 5},
    }


def _final(content):
    return {"choices": [{"message": {"role": "assistant", "content": content}}]}


class ScriptedLLM:
    def __init__(self, replies):
        self.replies = list(replies)
        self.seen = []

    def chat(self, messages, *, tools=None, max_tokens=1024):
        self.seen.append(messages)
        return self.replies.pop(0)


def test_react_calls_tal_and_returns_cited_answer():
    llm = ScriptedLLM(
        [
            _tool_call("get_metrics", {"start": -60, "end": NOW}),
            _final(
                '<think>cpu spike</think>```json\n{"top_services":["checkoutservice"],'
                '"claims":[{"service":"checkoutservice","claim":"cpu","evidence_refs":["E1"]}]}```'
            ),
        ]
    )
    result = run_react(llm, Source(), case_id="replay-1")
    assert result["status"] == "completed"
    assert result["top_services"] == ["checkoutservice"]
    assert (result["tool_calls"], result["invalid_tool_calls"]) == (1, 0)
    assert result["unsupported_claims"] == 0
    assert "now=1000" in llm.seen[0][0]["content"]
    tool_message = json.loads(next(m for m in result["messages"] if m["role"] == "tool")["content"])
    assert tool_message["metrics"][0]["metric"] == "checkoutservice_cpu"


def test_invalid_tool_arguments_are_counted_not_fatal():
    llm = ScriptedLLM(
        [
            _tool_call("get_metrics", {"service": "nope", "start": 1, "end": 2}),
            _final('{"top_services":["madeup"],"claims":[{"service":"x","evidence_refs":["E9"]}]}'),
        ]
    )
    result = run_react(llm, Source(), case_id="replay-1")
    assert result["invalid_tool_calls"] == 1
    assert result["unknown_services"] == ["madeup"]
    assert result["unsupported_claims"] == 1


def test_unparseable_answer_gets_one_repair_turn():
    llm = ScriptedLLM([_final("I think it is checkout."), _final('{"top_services":["frontend"]}')])
    result = run_react(llm, Source(), case_id="replay-1")
    assert (result["status"], result["parse_repairs"]) == ("completed", 1)
    assert result["top_services"] == ["frontend"]


def test_react_enforces_tool_budget():
    llm = ScriptedLLM([_tool_call("get_topology", {})] * 2 + [_final('{"top_services":["a"]}')])
    result = run_react(llm, Source(), case_id="replay-1", max_tool_calls=2)
    assert result["status"] == "tool_budget_exhausted"
    assert result["tool_calls"] == 2
    assert result["top_services"] == ["a"]


def test_tools_clip_to_clock_and_summarise_logs():
    out = dispatch(
        Source(), "search_logs", {"service": "checkoutservice", "start": -60, "end": 5000}
    )
    assert out["window"]["end"] == NOW
    assert out["count"] == 31 and out["baseline_count"] == 0
    assert out["top_messages"][0]["message"] == "error <n>"


def test_constant_baseline_does_not_explode_z_score():
    class Flat(Source):
        def metrics(self, service, start, end, step=1):
            times = range(start, min(end, NOW) + 1)
            values = {
                "frontend_socket": [23.0 if t <= NOW - 60 else 23.1 for t in times],
                "checkoutservice_cpu": [1.0 if t <= NOW - 60 else 9.0 for t in times],
            }
            result = [
                {
                    "metric": {"__name__": k},
                    "values": [[t, str(v)] for t, v in zip(times, vs, strict=True)],
                }
                for k, vs in values.items()
            ]
            return {"data": {"resultType": "matrix", "result": result}}

    out = dispatch(Flat(), "get_metrics", {"start": -60, "end": 0})
    assert out["metrics"][0]["metric"] == "checkoutservice_cpu"
    assert abs(out["metrics"][1]["z_score"]) < 1


def test_parse_answer_handles_noise():
    assert parse_answer('prefix {"a": 1} then {"top_services": ["x"]} suffix') == {
        "top_services": ["x"]
    }
    assert parse_answer("no json here") is None
