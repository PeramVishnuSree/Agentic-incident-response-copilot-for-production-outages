"""Shared runtime configuration, loaded from environment / .env."""

from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # LLM (model-agnostic)
    llm_provider: str = "anthropic"
    llm_model: str = "claude-sonnet-5-5"
    llm_api_key: str = ""
    llm_max_spend_usd: float = 5.0

    # Stores
    database_url: str = "postgresql+psycopg://copilot:copilot@localhost:5432/copilot"
    prometheus_url: str = "http://localhost:9090"
    alertmanager_url: str = "http://localhost:9093"
    elasticsearch_url: str = "http://localhost:9200"

    # Kubernetes / safety
    kubeconfig: str = "./kubeconfig"
    target_namespace: str = "online-boutique"
    namespace_allowlist: str = "online-boutique"

    @property
    def allowed_namespaces(self) -> set[str]:
        return {n.strip() for n in self.namespace_allowlist.split(",") if n.strip()}


def get_settings() -> Settings:
    return Settings()
