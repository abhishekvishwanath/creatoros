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

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint, text
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


class BrandOpportunity(Base, TimestampMixin, CreatorScopedMixin):
    """CLAUDE.md §71. One row per brand — re-scoring updates it in place
    rather than versioning (unlike CreatorProfile etc.), since this is a
    current-fit read, not an identity with history worth preserving. The
    unique constraint on brand_id is the upsert's dedup key and the
    backstop against a race between two concurrent score requests for the
    same brand (same bug class as CalendarEvent in an earlier phase).

    score_components always keeps `contactability` computed in code (does a
    verified/creator-provided contact exist?), never proposed by the model —
    same "no opaque model-invented number" discipline as content Opportunity
    scoring (CLAUDE.md §20, §71)."""

    __tablename__ = "brand_opportunities"
    __table_args__ = (UniqueConstraint("brand_id", name="uq_brand_opportunities_brand"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("brand_opportunity"))
    brand_id: Mapped[str] = mapped_column(String, ForeignKey("brands.id", ondelete="CASCADE"), index=True)
    score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    score_components: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    reasons: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    evidence_signal_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    suggested_contact_roles: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    # scored | qualified | archived
    status: Mapped[str] = mapped_column(String, default="scored")
    # True when the brand's category conflicts with a creator-stated
    # prohibited category (CLAUDE.md §71) — persisted (not just returned as
    # an ephemeral warning on the scoring response) so the Brand Radar and a
    # revisited detail view still surface it without re-scoring.
    prohibited_conflict: Mapped[bool] = mapped_column(Boolean, default=False)


class CampaignBrief(Base, TimestampMixin):
    """Part II Phase 5 (CLAUDE.md commercial spec §9). One current brief per
    BrandOpportunity — "Create pitch" regenerates it in place, mirroring
    ContentBrief's single-current-row convention (app/domain/content/models.py).
    Unlike ContentBrief there's no parallel ContentVersion-style history table
    yet: nothing reads a campaign brief's history until Phase 6's
    OutreachThread exists, so building that now would be speculative.

    `suggested_deliverables` is explicitly a proposal, never a commitment —
    enforced by UI copy (Part II §66: the system never commits anything on
    the creator's behalf), not just by this field's name."""

    __tablename__ = "campaign_briefs"
    __table_args__ = (UniqueConstraint("brand_opportunity_id", name="uq_campaign_briefs_brand_opportunity"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("campaign_brief"))
    brand_opportunity_id: Mapped[str] = mapped_column(
        String, ForeignKey("brand_opportunities.id", ondelete="CASCADE"), index=True
    )
    objective_hypothesis: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    campaign_concept: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    content_format: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    why_this_brand: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    why_now: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_cta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    suggested_deliverables: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    pitch_angle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    personalization_facts: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    evidence_signal_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)


class OutreachThread(Base, TimestampMixin, CreatorScopedMixin):
    """Part II Phase 6 (CLAUDE.md §66, §70). One thread per outreach attempt
    at a brand opportunity — NOT upserted-by-FK like CampaignBrief/
    BrandOpportunity, because a creator may genuinely run more than one
    outreach attempt at the same opportunity over time (a different
    contact, a retry months later); each is real history worth keeping,
    not a "current state" to overwrite.

    `campaign_brief_id` is a reference for UI traceability only — the
    actual pitch text lives on this thread's initial OutreachMessage.body,
    snapshotted at creation time. Regenerating the campaign brief later
    must not silently change what an already-drafted/approved/sent message
    says, so the message body (not a live join to CampaignBrief) is what a
    read ever shows.

    `status` is the pipeline stage: drafting -> approved -> sent -> replied
    -> won/lost/archived. Only drafting/approved/sent are reachable in
    Phase 6 (message approve/send transitions below); `replied` arrives
    with Phase 7's paste-in-a-reply flow, and won/lost/archived only ever
    get set by a future creator-decision route — never by this model's
    transitions and never by OutreachAgent (CLAUDE.md §66: the Outreach
    Agent researches, drafts, and classifies; it never negotiates, accepts,
    rejects, or writes outcome/creator_decision/status beyond drafting)."""

    __tablename__ = "outreach_threads"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("outreach_thread"))
    brand_opportunity_id: Mapped[str] = mapped_column(
        String, ForeignKey("brand_opportunities.id", ondelete="CASCADE"), index=True
    )
    contact_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("brand_contacts.id", ondelete="SET NULL"), nullable=True
    )
    campaign_brief_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("campaign_briefs.id", ondelete="SET NULL"), nullable=True
    )
    # drafting | approved | sent | replied | won | lost | archived
    status: Mapped[str] = mapped_column(String, default="drafting")
    outcome: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    creator_decision: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    creator_decision_note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decided_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    deal_value: Mapped[Optional[float]] = mapped_column(Float, nullable=True)


class OutreachMessage(Base, TimestampMixin):
    """One row per message in a thread, in both directions. `status` is
    only meaningful for outbound messages (draft -> approved -> sent —
    CLAUDE.md §70's human-in-the-loop gate: mark-sent requires approved
    first, enforced in app/domain/commercial/service.py, not just by
    prompt wording). `extracted_data` is populated only for inbound
    brand_reply messages, starting Phase 7."""

    __tablename__ = "outreach_messages"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("outreach_message"))
    thread_id: Mapped[str] = mapped_column(String, ForeignKey("outreach_threads.id", ondelete="CASCADE"), index=True)
    # outbound | inbound
    direction: Mapped[str] = mapped_column(String)
    # initial_pitch | follow_up | brand_reply
    kind: Mapped[str] = mapped_column(String)
    subject: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    body: Mapped[str] = mapped_column(Text)
    # draft | approved | sent — null for inbound messages, which have no
    # send lifecycle of their own.
    status: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    extracted_data: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
