"""Agent Output Contract (CLAUDE.md §40): every agent returns this shape, never
free-form prose the caller has to parse. `proposed_state_changes` is the only
path from an agent to the database (CLAUDE.md §8.3) — the agent describes what
it wants changed; a domain state service (e.g.
app/domain/creator/service.py::apply_creator_profile_update) decides how to
apply it."""

from typing import Literal

from pydantic import BaseModel, Field


class AgentOutput(BaseModel):
    status: Literal["success", "failed", "partial"]
    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    inputs_used: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    proposed_state_changes: list[dict] = Field(default_factory=list)
    next_action: str | None = None
    warnings: list[str] = Field(default_factory=list)
