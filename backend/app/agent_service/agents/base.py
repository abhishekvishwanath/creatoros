"""Base Agent (CLAUDE.md §57 definition of done: defined inputs, defined
outputs, strict output schema, tool boundaries). Concrete agents declare
`name` and `allowed_tools` (CLAUDE.md §41 tool permissions — an agent only
gets the tools its job requires) and implement `run`."""

import json
import re
from abc import ABC, abstractmethod

from app.agent_service.model_router.router import ModelResponse, ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.schemas.creator import CreatorStateSnapshot


class BaseAgent(ABC):
    name: str
    allowed_tools: list[str] = []

    @abstractmethod
    async def run(
        self, context: CreatorStateSnapshot, model_router: ModelRouter, **extra_context
    ) -> AgentOutput:
        """`extra_context` carries whatever task-specific slice this agent
        asked the Context Builder for beyond the base snapshot (e.g. actual
        transcript text for voice analysis) — see
        app/agent_service/context/builder.py. Agents that don't need anything
        beyond the base snapshot simply ignore it."""
        raise NotImplementedError

    @staticmethod
    async def _complete_safely(
        model_router: ModelRouter,
        *,
        tier: ModelTier,
        system: str,
        user: str,
        label: str,
        inputs_used: list[str],
        evidence_ids: list[str],
    ) -> tuple[ModelResponse | None, AgentOutput | None]:
        """Wraps model_router.complete() so a real API-level failure (rate
        limit, timeout, network error — as opposed to a malformed-but-present
        response) becomes a "failed" AgentOutput for *this sub-job only*,
        instead of an uncaught exception that the Orchestrator would turn
        into a total run failure and discard whatever other sub-jobs already
        succeeded (CLAUDE.md §43: a transient provider hiccup on one sub-job
        must not erase results the run already had in hand).

        Returns (response, None) on success, or (None, failed_output) on
        failure — callers `return failure` immediately when it's not None.
        """
        try:
            response = await model_router.complete(tier=tier, system=system, user=user)
        except Exception as exc:  # noqa: BLE001 - any provider/network failure, not just ours
            return None, AgentOutput(
                status="failed",
                summary=f"{label}: model call failed ({type(exc).__name__}).",
                confidence=0.0,
                inputs_used=inputs_used,
                evidence_ids=evidence_ids,
                warnings=[str(exc)],
            )
        return response, None

    @staticmethod
    def _parse_json(text: str, *, required_key: str) -> dict:
        cleaned = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON from model: {exc}") from exc
        if required_key not in data:
            raise ValueError(f"model JSON missing '{required_key}'")
        return data
