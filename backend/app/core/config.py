from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration. Model identity and connection details live here,
    never hard-coded in business/agent logic (CLAUDE.md 12)."""

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    environment: str = "development"

    database_url: str = "postgresql+asyncpg://creatoros:creatoros@localhost:5544/creatoros"

    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""
    # Project Settings -> API -> JWT Settings ("JWT Secret", legacy HS256
    # signing key every Supabase project has unless asymmetric signing keys
    # have been explicitly opted into). Verifying Supabase-issued access
    # tokens locally with this avoids a network round-trip to Supabase's
    # JWKS endpoint on every request. Empty means real auth isn't
    # configured yet — see app/api/deps.py::get_current_user_id, which
    # falls back to the X-Debug-User-Id dev/test path in that case (same
    # "graceful degrade when unconfigured" precedent as ModelRouter, §12).
    supabase_jwt_secret: str = ""

    # Two interchangeable model providers (CLAUDE.md §12: "model providers ...
    # can change" — agent code talks to ModelRouter.complete(), never to a
    # provider SDK directly, so nothing above the router needs to know which
    # of these is active). Anthropic takes priority if both are set: Groq is
    # meant as a free interim provider for testing agent prompts/parsing
    # against a real model before switching to Claude for production.
    anthropic_api_key: str = ""
    groq_api_key: str = ""

    # Anthropic model names per tier (CLAUDE.md 12: strategic synthesis,
    # standard reasoning, bulk/fast classification).
    model_strategic_anthropic: str = "claude-opus-5"
    model_standard_anthropic: str = "claude-sonnet-5"
    model_fast_anthropic: str = "claude-haiku-4-5-20251001"

    # Groq model names per tier — free-tier open-source models. Verified
    # live against Groq's current catalog (it changes over time; re-check
    # with client.models.list() if these start 404ing):
    # - qwen/qwen3.8-27b answers cleanly with no hidden reasoning preamble.
    # - The openai/gpt-oss-* models are chain-of-thought reasoning models
    #   whose thinking tokens eat the max_tokens budget before any content
    #   comes out, so they need a much larger budget for the same task —
    #   avoided here for cost/latency, not capability.
    # - allam-2-7b is smaller/faster and still answers cleanly for FAST-tier use.
    model_strategic_groq: str = "qwen/qwen3.8-27b"
    model_standard_groq: str = "qwen/qwen3.8-27b"
    model_fast_groq: str = "allam-2-7b"

    web_origin: str = "http://localhost:3000"

    @property
    def model_provider(self) -> str:
        """Which provider ModelRouter should call. "stub" means no key is
        configured for either provider — agents fall back to labeled stub
        output instead of failing (see ModelRouter.complete)."""
        if self.anthropic_api_key:
            return "anthropic"
        if self.groq_api_key:
            return "groq"
        return "stub"

    @property
    def agents_live(self) -> bool:
        return self.model_provider != "stub"


@lru_cache
def get_settings() -> Settings:
    return Settings()
