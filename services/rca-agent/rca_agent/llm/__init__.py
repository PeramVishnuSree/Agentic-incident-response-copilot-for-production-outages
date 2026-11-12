"""Model-agnostic LLM interface (Workbook 2 §6.1).

Adapters are interchangeable; CI uses MockLLM so runs are deterministic.
A per-run spend cap is enforced by BudgetedLLM.
"""

from __future__ import annotations

from typing import Protocol

from common.config import get_settings


class LLMClient(Protocol):
    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
        """Return a completion for the prompt."""
        ...


class MockLLM:
    """Deterministic stand-in used in tests and offline development."""

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
        # Produce a tiny structured hint so agent smoke tests can parse something.
        return (
            "ROOT_CAUSE_CANDIDATE: checkoutservice\n"
            "EVIDENCE: restarts and cascading cart/frontend errors\n"
            f"NOTES: {prompt[: min(120, max_tokens)]}"
        )


class BudgetedLLM:
    """Wraps any LLMClient and enforces a soft USD spend cap per process."""

    def __init__(
        self,
        inner: LLMClient,
        *,
        max_spend_usd: float,
        usd_per_1k_tokens: float = 0.003,
    ) -> None:
        self.inner = inner
        self.max_spend_usd = max_spend_usd
        self.usd_per_1k_tokens = usd_per_1k_tokens
        self.spent_usd = 0.0
        self.tokens_used = 0

    def complete(self, prompt: str, *, max_tokens: int = 1024) -> str:
        if self.spent_usd >= self.max_spend_usd:
            raise RuntimeError(
                f"LLM spend cap reached (${self.max_spend_usd:.2f}); refusing further calls"
            )
        out = self.inner.complete(prompt, max_tokens=max_tokens)
        # Rough accounting: prompt + completion token estimate.
        tokens = max(1, (len(prompt) + len(out)) // 4)
        self.tokens_used += tokens
        self.spent_usd += (tokens / 1000.0) * self.usd_per_1k_tokens
        return out


def get_llm(provider: str | None = None) -> LLMClient:
    """Factory. Hosted providers can be added without changing callers."""
    settings = get_settings()
    name = (provider or settings.llm_provider or "mock").lower()
    if name in {"mock", "echo", "test"}:
        inner: LLMClient = MockLLM()
    elif name == "anthropic" and not settings.llm_api_key:
        # Safe default when no key is configured (local / CI).
        inner = MockLLM()
    else:
        # Until a real SDK adapter is configured, fall back to mock so the
        # pipeline still runs offline. Swap this for Anthropic/OpenAI clients.
        inner = MockLLM()
    return BudgetedLLM(inner, max_spend_usd=settings.llm_max_spend_usd)
