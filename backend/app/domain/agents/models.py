"""Agent observability (CLAUDE.md 44): every agent run gets a stable
agent_run_id and logs enough to reconstruct why a decision was made."""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import generate_id
from app.infrastructure.db.base import Base, TimestampMixin


class AgentRun(Base, TimestampMixin):
    __tablename__ = "agent_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("agent_run"))
    creator_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("creators.id", ondelete="CASCADE"), nullable=True, index=True
    )
    agent_name: Mapped[str] = mapped_column(String)
    workflow_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="running")  # running | succeeded | failed
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    cost_estimate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    state_changes: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)


class AgentMessage(Base, TimestampMixin):
    __tablename__ = "agent_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("agent_message"))
    agent_run_id: Mapped[str] = mapped_column(String, ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String)  # system | user | assistant | tool
    content: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class AgentToolCall(Base, TimestampMixin):
    __tablename__ = "agent_tool_calls"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("agent_tool_call"))
    agent_run_id: Mapped[str] = mapped_column(String, ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    tool_name: Mapped[str] = mapped_column(String)
    input: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    output: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, default="succeeded")
    duration_ms: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)


class StateSnapshot(Base, TimestampMixin):
    """Creator State Snapshot (CLAUDE.md 32): the bounded, task-specific context
    handed to an agent, preserved so important runs stay reconstructable."""

    __tablename__ = "state_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("state_snapshot"))
    creator_id: Mapped[str] = mapped_column(String, ForeignKey("creators.id", ondelete="CASCADE"), index=True)
    snapshot_type: Mapped[str] = mapped_column(String)
    payload: Mapped[dict] = mapped_column(JSON)
    created_for_run_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("agent_runs.id", ondelete="SET NULL"), nullable=True
    )
