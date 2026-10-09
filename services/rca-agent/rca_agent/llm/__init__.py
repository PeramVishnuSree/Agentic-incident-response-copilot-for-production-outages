"""Model-agnostic LLM interface (S1 deliverable).

A thin protocol so the RCA agent is not coupled to one provider. Concrete
Anthropic / OpenAI / local adapters implement `complete`. A per-run spend cap
(settings.llm_max_spend_usd) is enforced by the adapter in S2.
"""

from __future__ import annotations

from typing import Protocol


class LLMClient(Protocol):
    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
        """Return a completion for the prompt."""
        ...


class EchoLLM:
    """Deterministic stand-in used in tests and offline development."""

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
        return f"[echo] {prompt[:max_tokens]}"


def get_llm(provider: str = "anthropic") -> LLMClient:
    """Factory. TODO(S2): return real adapters keyed by provider."""
    return EchoLLM()
