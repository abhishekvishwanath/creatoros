"""Commercial Intelligence / Brand Outbound layer (CLAUDE.md Part II §65-74).

Extends Creator State — this is not a second creator-identity system. Phase 1
ships just CommercialProfile (versioned exactly like CreatorProfile/
VoiceProfile in app/domain/creator/models.py: is_current + version, with a
partial unique index so only one current row exists per creator at a time).
Brand/BrandContact/BrandSignal/BrandOpportunity/CampaignBrief/OutreachThread/
OutreachMessage land in later phases of the same build.
"""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import generate_id
from app.infrastructure.db.base import Base, CreatorScopedMixin, TimestampMixin, utcnow


class CommercialProfile(Base, TimestampMixin, CreatorScopedMixin):
    """CLAUDE.md §67. Fields the creator can set directly and/or the Creator
    Intelligence Agent can later propose updates to (same apply-through-a-
    domain-service discipline as CreatorProfile — CLAUDE.md §8.3)."""

    __tablename__ = "commercial_profiles"
    __table_args__ = (
        Index(
            "ux_commercial_profiles_current",
            "creator_id",
            unique=True,
            postgresql_where=text("is_current"),
        ),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("commercial_profile"))
    version: Mapped[int] = mapped_column(Integer, default=1)
    is_current: Mapped[bool] = mapped_column(Boolean, default=True)

    ideal_sponsor_categories: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    prohibited_categories: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    target_geographies: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    preferred_deal_formats: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    minimum_conditions: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    exclusivity_constraints: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    usage_rights_preferences: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sponsorship_goals: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    revenue_goal: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    brands_to_avoid: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)

    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    evidence_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)


class Brand(Base, TimestampMixin, CreatorScopedMixin):
    """CLAUDE.md §68-69. Creator-scoped, not a shared global table — same
    tenant-isolation reasoning as Competitor (CLAUDE.md §46; two creators
    tracking the same real company get two independent rows). `source`
    distinguishes what the creator typed in from what an agent suggested
    from its own general knowledge (Phase 3) — the latter must never be
    presented as verified (CLAUDE.md §69)."""

    __tablename__ = "brands"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("brand"))
    name: Mapped[str] = mapped_column(String)
    website: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    category: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    subcategory: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    geography: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    target_customer: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    products: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    positioning: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    competitors: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    # creator_provided | agent_suggested
    source: Mapped[str] = mapped_column(String, default="creator_provided")
    confidence: Mapped[float] = mapped_column(Float, default=1.0)
    # candidate | archived
    status: Mapped[str] = mapped_column(String, default="candidate")


class BrandContact(Base, TimestampMixin):
    """CLAUDE.md §68, §70. Never invent a contact (§10 of the original
    commercial spec, §23 safety rules) — verification_state makes the
    provenance visible in the UI rather than presenting everything as
    equally certain."""

    __tablename__ = "brand_contacts"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("brand_contact"))
    brand_id: Mapped[str] = mapped_column(String, ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    name: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    department: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    profile_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # unverified | creator_provided | verified
    verification_state: Mapped[str] = mapped_column(String, default="unverified")
    confidence: Mapped[float] = mapped_column(Float, default=0.5)
    last_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class BrandSignal(Base, TimestampMixin, CreatorScopedMixin):
    """CLAUDE.md §68. Manual entry, same pattern as ResearchSignal (§69) —
    a creator/operator-observed fact about a brand, not a live-crawled one.
    No separate BrandSource join table (unlike ResearchSource) — inline
    provenance fields keep this to one table for MVP, same simplification
    already used for PerformanceSnapshot.baseline_comparison."""

    __tablename__ = "brand_signals"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("brand_signal"))
    brand_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("brands.id", ondelete="CASCADE"), nullable=True, index=True
    )
    signal_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    summary: Mapped[str] = mapped_column(Text)
    source_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    source_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    observed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    retrieved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    evidence_quality: Mapped[Optional[str]] = mapped_column(String, nullable=True)
