"""Research + Opportunity engine (CLAUDE.md 16, 17, 20). Every opportunity must
trace back to evidence — this is what makes 'why this recommendation?' answerable
in the UI (CLAUDE.md 3.4, 16)."""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.ids import generate_id
from app.infrastructure.db.base import Base, CreatorScopedMixin, TimestampMixin


class Competitor(Base, TimestampMixin, CreatorScopedMixin):
    __tablename__ = "competitors"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("competitor"))
    name: Mapped[str] = mapped_column(String)
    platform: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    handle: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class ResearchSource(Base, TimestampMixin):
    """Provenance record (CLAUDE.md 16 source/evidence model)."""

    __tablename__ = "research_sources"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("research_source"))
    platform: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    publisher: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
    source_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # public | connected | creator_provided
    evidence_quality: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # high | medium | low


class ResearchSignal(Base, TimestampMixin, CreatorScopedMixin):
    """Normalized external signal (CLAUDE.md 17.2)."""

    __tablename__ = "research_signals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("research_signal"))
    source_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("research_sources.id", ondelete="SET NULL"), nullable=True
    )
    topic: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    subtopic: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    format: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    engagement: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    content_features: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    audience_signals: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    hook_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    topic_cluster: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    evidence_quality: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class Opportunity(Base, TimestampMixin, CreatorScopedMixin):
    """CLAUDE.md 20 opportunity engine. score_components must stay broken out —
    never collapse to one opaque number in the UI (CLAUDE.md 20 last line)."""

    __tablename__ = "opportunities"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("opportunity"))
    topic: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    subtopic: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    angle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    format: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    audience_segment_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("audience_segments.id", ondelete="SET NULL"), nullable=True
    )
    content_pillar_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("content_pillars.id", ondelete="SET NULL"), nullable=True
    )
    strategic_goal: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    # e.g. {"audience_fit": 0.8, "creator_fit": 0.7, "demand": 0.6, "novelty": 0.5,
    #       "evidence": 0.9, "competition": 0.3, "saturation": 0.2, "production_complexity": 0.4}
    score_components: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    competition_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    saturation_estimate: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    production_complexity: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    recommended_time_window: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    confidence: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # pending | approved | rejected | saved_for_later | used
    status: Mapped[str] = mapped_column(String, default="pending")

    evidence: Mapped[list["OpportunityEvidence"]] = relationship(
        back_populates="opportunity", cascade="all, delete-orphan"
    )


class OpportunityEvidence(Base, TimestampMixin):
    """Links an opportunity to the concrete evidence that produced it, so the UI
    can always answer 'why this recommendation?' (CLAUDE.md 3.4, 16)."""

    __tablename__ = "opportunity_evidence"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("opportunity_evidence"))
    opportunity_id: Mapped[str] = mapped_column(
        String, ForeignKey("opportunities.id", ondelete="CASCADE"), index=True
    )
    research_signal_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("research_signals.id", ondelete="SET NULL"), nullable=True
    )
    content_item_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True
    )
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    opportunity: Mapped["Opportunity"] = relationship(back_populates="evidence")
