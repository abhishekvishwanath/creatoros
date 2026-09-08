"""Creator entity + Creator DNA tables (CLAUDE.md 4, 5, 7).

The Creator is the top-level entity everything else hangs off of (CLAUDE.md 3.1,
4.1). Identity/voice/audience are versioned (is_current + version) rather than
overwritten, so a materially wrong or stale profile never silently erases the
history that produced it (CLAUDE.md 15).
"""

from datetime import date, datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.ids import generate_id
from app.infrastructure.db.base import Base, CreatorScopedMixin, TimestampMixin


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("user"))
    email: Mapped[str] = mapped_column(String, unique=True, index=True)
    supabase_auth_id: Mapped[Optional[str]] = mapped_column(String, unique=True, nullable=True)

    creators: Mapped[list["Creator"]] = relationship(back_populates="user")


class Creator(Base, TimestampMixin):
    """The top-level entity (CLAUDE.md 4.1). Every creator-scoped table carries
    creator_id and every creator-scoped query must filter on it."""

    __tablename__ = "creators"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("creator"))
    user_id: Mapped[str] = mapped_column(String, ForeignKey("users.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String)
    niche: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sub_niche: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    geography: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    languages: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    business_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    monetization_model: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Onboarding state machine: created -> connecting_accounts -> analyzing -> reviewing -> active
    onboarding_status: Mapped[str] = mapped_column(String, default="created")

    user: Mapped["User"] = relationship(back_populates="creators")


class SocialAccount(Base, TimestampMixin, CreatorScopedMixin):
    __tablename__ = "social_accounts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("social_account"))
    platform: Mapped[str] = mapped_column(String)  # youtube | instagram | x | reddit | manual
    external_account_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    display_name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="connected")  # connected | disconnected | error
    connected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class CreatorProfile(Base, TimestampMixin, CreatorScopedMixin):
    """Identity + positioning + boundaries (CLAUDE.md 7.1, 7.5). Versioned.

    At most one row per creator may have is_current=True — enforced at the DB
    level (not just in application code) so two concurrent analyze/update
    calls can't both insert a "current" row for the same creator.
    """

    __tablename__ = "creator_profiles"
    __table_args__ = (
        Index(
            "ux_creator_profiles_current",
            "creator_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("creator_profile"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)

    bio: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    expertise: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    positioning_statement: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # CLAUDE.md 7.5 creator boundaries
    prohibited_topics: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    avoided_claims: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    rejected_tones: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    disclosure_requirements: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)


class VoiceProfile(Base, TimestampMixin, CreatorScopedMixin):
    """CLAUDE.md 7.3 brand and voice. Versioned. See CreatorProfile's
    docstring above for why is_current is uniquely constrained per creator."""

    __tablename__ = "voice_profiles"
    __table_args__ = (
        Index(
            "ux_voice_profiles_current",
            "creator_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("voice_profile"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)

    tone: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    vocabulary: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    sentence_style: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    pacing: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    personality: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    humor_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    controversy_tolerance: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    storytelling_style: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    opinion_style: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    signature_phrases: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    cta_style: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)


class AudienceProfile(Base, TimestampMixin, CreatorScopedMixin):
    """CLAUDE.md 7.2 audience. Versioned, creator-wide (not segment-specific).

    See CreatorProfile's docstring for why is_current is uniquely constrained
    per creator — this table originally shipped without it (a gap fixed
    alongside the Audience Intelligence Agent, the first thing to actually
    write to it)."""

    __tablename__ = "audience_profiles"
    __table_args__ = (
        Index(
            "ux_audience_profiles_current",
            "creator_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("audience_profile"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)

    geography: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    demographics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    psychographics: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    knowledge_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    purchase_intent: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    preferred_language: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    evidence_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)


class AudienceSegment(Base, TimestampMixin, CreatorScopedMixin):
    """Audience Problem Graph nodes (CLAUDE.md 19), scoped per named segment."""

    __tablename__ = "audience_segments"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("audience_segment"))
    name: Mapped[str] = mapped_column(String)
    problems: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    desires: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    objections: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    questions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    fears: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    aspirations: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    language: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    knowledge_level: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    sample_size: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    evidence_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)


class AudienceSignal(Base, TimestampMixin, CreatorScopedMixin):
    """Raw audience voice (CLAUDE.md 19): a comment, question, or piece of
    feedback the creator (or their team) observed, pasted in manually since
    no comments/analytics API is connected yet — same pattern as
    ResearchSignal for market/competitor signals (app/domain/research/models.py),
    kept as its own concept because a raw audience quote and a competitor
    content observation are different kinds of evidence for different
    agents. This is the raw material the Audience Intelligence Agent reads;
    AudienceProfile and AudienceSegment are its synthesized output."""

    __tablename__ = "audience_signals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("audience_signal"))
    text: Mapped[str] = mapped_column(Text)
    source_platform: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class CreatorGoal(Base, TimestampMixin, CreatorScopedMixin):
    __tablename__ = "creator_goals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("creator_goal"))
    goal_type: Mapped[str] = mapped_column(String)  # reach | authority | community | conversion | ...
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    target_metric: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    target_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String, default="active")  # active | achieved | dropped
    start_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    end_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)


class CreatorPreference(Base, TimestampMixin, CreatorScopedMixin):
    """Explicit + inferred preferences, including approve/reject signals from
    opportunity review (CLAUDE.md 33 Phase 5: 'These actions should themselves
    become useful preference signals')."""

    __tablename__ = "creator_preferences"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("creator_preference"))
    key: Mapped[str] = mapped_column(String)
    value: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    source: Mapped[str] = mapped_column(String, default="explicit")  # explicit | inferred
