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

    anthropic_api_key: str = ""

    # Model router tiers (CLAUDE.md 12): strategic synthesis, standard reasoning,
    # bulk/fast classification. Swap model names here, not in agent code.
    model_strategic: str = "claude-opus-4-1"
    model_standard: str = "claude-sonnet-4-5"
    model_fast: str = "claude-haiku-4-5"

    web_origin: str = "http://localhost:3000"

    @property
    def agents_live(self) -> bool:
        """Whether the agent service should make live Claude calls or return
        structured stubs. Flips on automatically once a key is configured."""
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    return Settings()
