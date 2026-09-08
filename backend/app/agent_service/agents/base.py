"""Base Agent (CLAUDE.md §57 definition of done: defined inputs, defined
outputs, strict output schema, tool boundaries). Concrete agents declare
`name` and `allowed_tools` (CLAUDE.md §41 tool permissions — an agent only
gets the tools its job requires) and implement `run`."""

from abc import ABC, abstractmethod

from app.agent_service.model_router.router import ModelRouter
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
