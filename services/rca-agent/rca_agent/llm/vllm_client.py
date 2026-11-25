from __future__ import annotations

import httpx


class VLLMClient:
    """OpenAI-compatible client for a local vLLM server."""

    def __init__(
        self, *, base_url: str, model: str, api_key: str = "EMPTY", timeout: float = 120.0
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.api_key = api_key
        self.timeout = timeout

    def chat(
        self, messages: list[dict], *, tools: list[dict] | None = None, max_tokens: int = 1024
    ) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0,
            "max_tokens": max_tokens,
        }
        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"
        response = httpx.post(
            f"{self.base_url}/chat/completions",
            headers={"Authorization": f"Bearer {self.api_key}"},
            json=payload,
            timeout=self.timeout,
        )
        if response.status_code >= 400:
            response.raise_for_status()
        return response.json()

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
        result = self.chat([{"role": "user", "content": prompt}], max_tokens=max_tokens)
        return str(result["choices"][0]["message"].get("content", ""))
