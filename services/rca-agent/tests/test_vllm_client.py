import httpx
from rca_agent.llm.vllm_client import VLLMClient


def test_vllm_client_posts_openai_compatible_payload(monkeypatch):
    seen = {}

    def fake_post(url, **kwargs):
        seen.update(url=url, kwargs=kwargs)
        return httpx.Response(200, json={"choices": [{"message": {"content": "ok"}}]})

    monkeypatch.setattr(httpx, "post", fake_post)
    client = VLLMClient(base_url="http://localhost:8000/v1", model="qwen")
    assert client.complete("hello") == "ok"
    assert seen["url"].endswith("/chat/completions")
    assert seen["kwargs"]["json"]["model"] == "qwen"
