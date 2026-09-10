"""Commercial Intelligence / Brand Outbound layer (CLAUDE.md Part II §65-74).

Extends Creator State — this is not a second creator-identity system. Phase 1
ships just CommercialProfile (versioned exactly like CreatorProfile/
VoiceProfile in app/domain/creator/models.py: is_current + version, with a
partial unique index so only one current row exists per creator at a time).
Brand/BrandContact/BrandSignal/BrandOpportunity/CampaignBrief/OutreachThread/
OutreachMessage land in later phases of the same build.
"""

from typing import Optional

from sqlalchemy import JSON, Boolean, Float, Index, Integer, String, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import generate_id
from app.infrastructure.db.base import Base, CreatorScopedMixin, TimestampMixin


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
