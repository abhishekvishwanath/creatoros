"""Experimentation + Learning Engine (CLAUDE.md 30, 31). A learning must never be
promoted to creator-wide truth without adequate evidence (CLAUDE.md 31) — hence
confidence + scope + evidence_ids on every row here."""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Date, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import generate_id
from app.infrastructure.db.base import Base, CreatorScopedMixin, TimestampMixin


class Experiment(Base, TimestampMixin, CreatorScopedMixin):
    __tablename__ = "experiments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("experiment"))
    hypothesis: Mapped[str] = mapped_column(Text)
    variable: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    control_reference: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    planned_test_set: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    status: Mapped[str] = mapped_column(String, default="planned")  # planned | running | completed | abandoned
    results: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    confidence: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # low | medium | high
    conclusion: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_action: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ExperimentResult(Base, TimestampMixin):
    __tablename__ = "experiment_results"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("experiment_result"))
    experiment_id: Mapped[str] = mapped_column(String, ForeignKey("experiments.id", ondelete="CASCADE"), index=True)
    content_item_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True
    )
    metric_name: Mapped[str] = mapped_column(String)
    metric_value: Mapped[float] = mapped_column(Float)
    group: Mapped[str] = mapped_column(String)  # test | control


class StrategicLearning(Base, TimestampMixin, CreatorScopedMixin):
    """CLAUDE.md 31. Never overwrite creator state directly — a learning is the
    auditable unit that updates it (CLAUDE.md 8.2 example event: learning.created)."""

    __tablename__ = "strategic_learnings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("strategic_learning"))
    statement: Mapped[str] = mapped_column(Text)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    evidence_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    first_observed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    last_validated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    # active | superseded | retracted
    status: Mapped[str] = mapped_column(String, default="active")
    # creator-wide | platform-specific | format-specific | topic-specific |
    # audience-segment-specific | temporary experiment (CLAUDE.md 31)
    scope: Mapped[str] = mapped_column(String, default="temporary experiment")
