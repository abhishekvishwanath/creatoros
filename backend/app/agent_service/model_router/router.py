"""Model Router (CLAUDE.md §12): model identity lives in configuration, never
hard-coded in agent logic. Callers ask for a *tier* (strategic / standard /
fast) and the router resolves it to whatever model is currently configured
for the active provider — swapping providers or model versions later means
editing Settings, not every agent.

Two providers are supported: Anthropic (production) and Groq (a free,
interim provider for validating agent prompts/JSON-parsing against a real
model before spending on Claude — see Settings.model_provider for the
precedence rule). When neither is configured, `complete()` returns a stub
response instead of failing, so the rest of the pipeline (context building,
orchestration, DB writes, observability) is fully exercised in dev without
any key. Every ModelResponse carries `stub` so callers and logs can tell the
difference (CLAUDE.md §44: never let a stub silently look like a real result).
"""

from dataclasses import dataclass
from enum import Enum
from functools import lru_cache
from time import monotonic

from app.core.config import Settings, get_settings


class ModelTier(str, Enum):
    STRATEGIC = "strategic"
    STANDARD = "standard"
    FAST = "fast"


@dataclass
class ModelResponse:
    text: str
    model: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    stub: bool


class ModelRouter:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._anthropic_client = None
        self._groq_client = None

    def _model_for(self, tier: ModelTier) -> str:
        provider = self._settings.model_provider
        if provider == "anthropic":
            return {
                ModelTier.STRATEGIC: self._settings.model_strategic_anthropic,
                ModelTier.STANDARD: self._settings.model_standard_anthropic,
                ModelTier.FAST: self._settings.model_fast_anthropic,
            }[tier]
        if provider == "groq":
            return {
                ModelTier.STRATEGIC: self._settings.model_strategic_groq,
                ModelTier.STANDARD: self._settings.model_standard_groq,
                ModelTier.FAST: self._settings.model_fast_groq,
            }[tier]
        return "none"

    async def complete(
        self,
        *,
        tier: ModelTier,
        system: str,
        user: str,
        max_tokens: int = 1024,
    ) -> ModelResponse:
        provider = self._settings.model_provider
        started = monotonic()

        if provider == "stub":
            return ModelResponse(
                text=self._stub_text(),
                model="stub:none",
                input_tokens=0,
                output_tokens=0,
                latency_ms=int((monotonic() - started) * 1000),
                stub=True,
            )

        model = self._model_for(tier)

        if provider == "anthropic":
            text, input_tokens, output_tokens = await self._complete_anthropic(
                model=model, system=system, user=user, max_tokens=max_tokens
            )
        else:
            text, input_tokens, output_tokens = await self._complete_groq(
                model=model, system=system, user=user, max_tokens=max_tokens
            )

        return ModelResponse(
            text=text,
            model=f"{provider}:{model}",
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=int((monotonic() - started) * 1000),
            stub=False,
        )

    async def _complete_anthropic(
        self, *, model: str, system: str, user: str, max_tokens: int
    ) -> tuple[str, int, int]:
        if self._anthropic_client is None:
            from anthropic import AsyncAnthropic

            self._anthropic_client = AsyncAnthropic(api_key=self._settings.anthropic_api_key)

        response = await self._anthropic_client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return text, response.usage.input_tokens, response.usage.output_tokens

    async def _complete_groq(
        self, *, model: str, system: str, user: str, max_tokens: int
    ) -> tuple[str, int, int]:
        if self._groq_client is None:
            from groq import AsyncGroq

            self._groq_client = AsyncGroq(api_key=self._settings.groq_api_key)

        response = await self._groq_client.chat.completions.create(
            model=model,
            max_tokens=max_tokens,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        )
        text = response.choices[0].message.content or ""
        usage = response.usage
        return text, (usage.prompt_tokens if usage else 0), (usage.completion_tokens if usage else 0)

    @staticmethod
    def _stub_text() -> str:
        return (
            "STUB RESPONSE (no ANTHROPIC_API_KEY or GROQ_API_KEY configured — see "
            "backend/.env.example). The caller is responsible for falling back to a "
            "rule-based result when ModelResponse.stub is True rather than trying to "
            "parse this as real output."
        )


@lru_cache
def get_model_router() -> ModelRouter:
    return ModelRouter(get_settings())
