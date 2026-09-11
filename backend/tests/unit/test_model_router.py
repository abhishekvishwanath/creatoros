import pytest

from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.core.config import Settings


def _settings(**overrides) -> Settings:
    # _env_file=None: these tests assert on the *absence* of keys, so they
    # must never pick up the developer's real backend/.env (which usually
    # has at least GROQ_API_KEY set) — only explicit overrides above should
    # affect the result.
    return Settings(_env_file=None, database_url="postgresql+asyncpg://x:x@localhost:5544/x", **overrides)


def test_provider_defaults_to_stub_with_no_keys():
    settings = _settings()
    assert settings.model_provider == "stub"
    assert settings.agents_live is False


def test_provider_is_groq_when_only_groq_key_set():
    settings = _settings(groq_api_key="gsk_test")
    assert settings.model_provider == "groq"
    assert settings.agents_live is True


def test_anthropic_takes_priority_when_both_keys_set():
    settings = _settings(anthropic_api_key="sk-ant-test", groq_api_key="gsk_test")
    assert settings.model_provider == "anthropic"


def test_model_for_resolves_per_active_provider():
    router = ModelRouter(_settings(groq_api_key="gsk_test"))
    assert router._model_for(ModelTier.STANDARD) == "qwen/qwen3.8-27b"

    router = ModelRouter(_settings(anthropic_api_key="sk-ant-test"))
    assert router._model_for(ModelTier.STANDARD) == "claude-sonnet-5"


@pytest.mark.asyncio
async def test_complete_returns_labeled_stub_when_no_provider_configured():
    router = ModelRouter(_settings())
    response = await router.complete(tier=ModelTier.STANDARD, system="sys", user="hi")
    assert response.stub is True
    assert response.model == "stub:none"
