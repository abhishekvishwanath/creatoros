"""Model Router (CLAUDE.md §12): model identity lives in configuration, never
hard-coded in agent logic. Callers ask for a *tier* (strategic / standard /
fast) and the router resolves it to whatever model is currently configured
for that tier — swapping model providers or versions later means editing
Settings, not every agent.

When no ANTHROPIC_API_KEY is configured, `complete()` returns a stub response
instead of failing, so the rest of the pipeline (context building,
orchestration, DB writes, observability) is fully exercised in dev without a
key. Every ModelResponse carries `stub` so callers and logs can tell the
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
        self._client = None

    def _model_for(self, tier: ModelTier) -> str:
        return {
            ModelTier.STRATEGIC: self._settings.model_strategic,
            ModelTier.STANDARD: self._settings.model_standard,
            ModelTier.FAST: self._settings.model_fast,
        }[tier]

    def _get_client(self):
        if self._client is None:
            from anthropic import AsyncAnthropic

            self._client = AsyncAnthropic(api_key=self._settings.anthropic_api_key)
        return self._client

    async def complete(
        self,
        *,
        tier: ModelTier,
        system: str,
        user: str,
        max_tokens: int = 1024,
    ) -> ModelResponse:
        model = self._model_for(tier)
        started = monotonic()

        if not self._settings.agents_live:
            return ModelResponse(
                text=self._stub_text(system=system, user=user),
                model=f"stub:{model}",
                input_tokens=0,
                output_tokens=0,
                latency_ms=int((monotonic() - started) * 1000),
                stub=True,
            )

        client = self._get_client()
        response = await client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(block.text for block in response.content if block.type == "text")
        return ModelResponse(
            text=text,
            model=model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            latency_ms=int((monotonic() - started) * 1000),
            stub=False,
        )

    @staticmethod
    def _stub_text(*, system: str, user: str) -> str:
        return (
            "STUB RESPONSE (no ANTHROPIC_API_KEY configured — see backend/.env.example). "
            "The caller is responsible for falling back to a rule-based result when "
            "ModelResponse.stub is True rather than trying to parse this as real output."
        )


@lru_cache
def get_model_router() -> ModelRouter:
    return ModelRouter(get_settings())
