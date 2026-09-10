"""Commercial state service (CLAUDE.md §67, §8.3): the only path a
commercial-profile update takes into the database, whether it comes from the
creator directly (Phase 1: a manual form, confidence=1.0 — their own stated
facts, not an inference) or later from an agent's proposed update (Phase 3+:
lower confidence, evidence_ids attached, same shape either way).

Versioning/supersede logic is shared with CreatorProfile/VoiceProfile/
AudienceProfile via app/domain/shared/versioned_profile.py rather than
re-derived here (CLAUDE.md §3.7 one source of truth, Part II §65).
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import generate_id
from app.domain.commercial.models import (
    Brand,
    BrandContact,
    BrandOpportunity,
    BrandSignal,
    CampaignBrief,
    CommercialProfile,
)
from app.domain.shared.versioned_profile import apply_versioned_profile_update, get_current_versioned_profile

_PROFILE_FIELDS = (
    "ideal_sponsor_categories",
    "prohibited_categories",
    "target_geographies",
    "preferred_deal_formats",
    "minimum_conditions",
    "exclusivity_constraints",
    "usage_rights_preferences",
    "sponsorship_goals",
    "revenue_goal",
    "brands_to_avoid",
)


async def get_current_commercial_profile(db: AsyncSession, *, creator_id: str) -> Optional[CommercialProfile]:
    return await get_current_versioned_profile(db, CommercialProfile, creator_id)


async def apply_commercial_profile_update(
    db: AsyncSession,
    *,
    creator_id: str,
    data: dict,
    confidence: float = 1.0,
    evidence_ids: Optional[list[str]] = None,
) -> CommercialProfile:
    return await apply_versioned_profile_update(
        db,
        model_cls=CommercialProfile,
        id_prefix="commercial_profile",
        creator_id=creator_id,
        data=data,
        fields=_PROFILE_FIELDS,
        confidence=confidence,
        evidence_ids=evidence_ids or [],
    )


# --- Brand database (CLAUDE.md §68-69, Part II Phase 2) ---------------------
# Plain CRUD, no agent involved — manual entry mirrors ResearchSignal
# ingestion exactly (app/domain/research/service.py::ingest_research_signal).


async def create_brand(db: AsyncSession, *, creator_id: str, data: dict) -> Brand:
    brand = Brand(
        id=generate_id("brand"),
        creator_id=creator_id,
        name=data["name"],
        website=data.get("website"),
        category=data.get("category"),
        subcategory=data.get("subcategory"),
        description=data.get("description"),
        geography=data.get("geography"),
        target_customer=data.get("target_customer"),
        products=data.get("products"),
        positioning=data.get("positioning"),
        competitors=data.get("competitors"),
        source=data.get("source", "creator_provided"),
        confidence=data.get("confidence", 1.0),
    )
    db.add(brand)
    await db.flush()
    return brand


async def list_brands(db: AsyncSession, *, creator_id: str, status: Optional[str] = None) -> list[Brand]:
    query = select(Brand).where(Brand.creator_id == creator_id)
    if status:
        query = query.where(Brand.status == status)
    result = await db.execute(query.order_by(desc(Brand.created_at)))
    return list(result.scalars().all())


async def get_brand(db: AsyncSession, *, creator_id: str, brand_id: str) -> Optional[Brand]:
    result = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.creator_id == creator_id))
    return result.scalar_one_or_none()


async def add_brand_contact(db: AsyncSession, *, brand_id: str, data: dict) -> BrandContact:
    contact = BrandContact(
        id=generate_id("brand_contact"),
        brand_id=brand_id,
        name=data.get("name"),
        role=data.get("role"),
        department=data.get("department"),
        email=data.get("email"),
        profile_url=data.get("profile_url"),
        source=data.get("source"),
        verification_state=data.get("verification_state", "unverified"),
        confidence=data.get("confidence", 0.5),
    )
    db.add(contact)
    await db.flush()
    return contact


async def list_brand_contacts(db: AsyncSession, *, brand_id: str) -> list[BrandContact]:
    result = await db.execute(
        select(BrandContact).where(BrandContact.brand_id == brand_id).order_by(desc(BrandContact.created_at))
    )
    return list(result.scalars().all())


async def add_brand_signal(db: AsyncSession, *, creator_id: str, brand_id: Optional[str], data: dict) -> BrandSignal:
    signal = BrandSignal(
        id=generate_id("brand_signal"),
        creator_id=creator_id,
        brand_id=brand_id,
        signal_type=data.get("signal_type"),
        summary=data["summary"],
        source_url=data.get("source_url"),
        source_note=data.get("source_note"),
        observed_at=data.get("observed_at"),
        retrieved_at=datetime.now(timezone.utc),
        evidence_quality=data.get("evidence_quality", "medium"),
    )
    db.add(signal)
    await db.flush()
    return signal


async def list_brand_signals(db: AsyncSession, *, creator_id: str, brand_id: Optional[str] = None) -> list[BrandSignal]:
    query = select(BrandSignal).where(BrandSignal.creator_id == creator_id)
    if brand_id:
        query = query.where(BrandSignal.brand_id == brand_id)
    result = await db.execute(query.order_by(desc(BrandSignal.created_at)))
    return list(result.scalars().all())


# --- Brand opportunity scoring (CLAUDE.md §71, Part II Phase 3) -------------

# Canonical set of model-groundable dimensions (CLAUDE.md §71) — defined here,
# not in the agent, so the domain layer (not the agent layer) owns what
# "a complete score" means; brand_intelligence.py imports this rather than
# keeping its own copy.
BRAND_OPPORTUNITY_SCORE_DIMENSIONS = (
    "audience_fit",
    "creator_fit",
    "product_content_fit",
    "timing_signal",
    "historical_category_fit",
)
_NEUTRAL_SCORE = 0.5


async def get_brand_opportunity(db: AsyncSession, *, brand_id: str) -> Optional[BrandOpportunity]:
    result = await db.execute(select(BrandOpportunity).where(BrandOpportunity.brand_id == brand_id))
    return result.scalar_one_or_none()


async def apply_brand_opportunity_score(
    db: AsyncSession,
    *,
    creator_id: str,
    brand_id: str,
    score_components: dict,
    contactability: float,
    reasons: str,
    evidence_signal_ids: list[str],
    suggested_contact_roles: list[str],
    confidence: float,
    prohibited_conflict: bool = False,
) -> BrandOpportunity:
    """Upserts by brand_id (CLAUDE.md §71) — a re-score reflects this
    brand's current best-known fit, not a point-in-time snapshot worth
    versioning the way Creator DNA is (CLAUDE.md §15's versioning rule
    applies to identity/history; a brand's fit score is neither).

    `score_components` may be missing a dimension the agent's grounding
    dropped (out of range, non-numeric, or absent from the model's
    response — see brand_intelligence.py). The combined `score` is always
    averaged over the full fixed dimension set (a missing one counts as a
    neutral 0.5), so two brands are comparable purely on fit rather than on
    how many dimensions each one happened to survive grounding — a brand
    scored on 3 dimensions must not be able to out-rank one honestly scored
    on all 5 just by having fewer numbers to average. `score_components` as
    *stored/displayed* keeps only what was actually grounded (plus the
    always-code-computed `contactability`), preserving CLAUDE.md §20's
    "never show an opaque/invented number" rule for the breakdown shown in
    the UI — the neutral fill-in is used for score math only, never
    presented as if the model scored it.
    """
    complete_dimensions = {
        dim: score_components.get(dim, _NEUTRAL_SCORE) for dim in BRAND_OPPORTUNITY_SCORE_DIMENSIONS
    }
    score = round((sum(complete_dimensions.values()) + contactability) / (len(complete_dimensions) + 1), 3)
    stored_components = {**score_components, "contactability": contactability}

    opportunity = await get_brand_opportunity(db, brand_id=brand_id)
    if opportunity is None:
        opportunity = BrandOpportunity(
            id=generate_id("brand_opportunity"),
            creator_id=creator_id,
            brand_id=brand_id,
        )
        db.add(opportunity)

    opportunity.score = score
    opportunity.score_components = stored_components
    opportunity.reasons = reasons
    opportunity.evidence_signal_ids = evidence_signal_ids
    opportunity.suggested_contact_roles = suggested_contact_roles
    opportunity.confidence = confidence
    opportunity.prohibited_conflict = prohibited_conflict
    await db.flush()
    return opportunity


async def list_brand_opportunities(db: AsyncSession, *, creator_id: str) -> list[tuple[BrandOpportunity, Brand]]:
    """Ranked for the Brand Radar UI — highest score first. Joined with
    Brand so the UI doesn't need a second round trip per card."""
    result = await db.execute(
        select(BrandOpportunity, Brand)
        .join(Brand, Brand.id == BrandOpportunity.brand_id)
        .where(BrandOpportunity.creator_id == creator_id)
        .order_by(desc(BrandOpportunity.score))
    )
    return [(opp, brand) for opp, brand in result.all()]


async def get_brand_opportunity_by_id(
    db: AsyncSession, *, creator_id: str, opportunity_id: str
) -> Optional[BrandOpportunity]:
    result = await db.execute(
        select(BrandOpportunity).where(
            BrandOpportunity.id == opportunity_id, BrandOpportunity.creator_id == creator_id
        )
    )
    return result.scalar_one_or_none()


# --- Campaign intelligence / pitch generation (CLAUDE.md §73, Part II Phase 5) --


async def get_campaign_brief(db: AsyncSession, *, brand_opportunity_id: str) -> Optional[CampaignBrief]:
    result = await db.execute(
        select(CampaignBrief).where(CampaignBrief.brand_opportunity_id == brand_opportunity_id)
    )
    return result.scalar_one_or_none()


_CAMPAIGN_BRIEF_FIELDS = (
    "objective_hypothesis",
    "campaign_concept",
    "content_format",
    "why_this_brand",
    "why_now",
    "suggested_cta",
    "suggested_deliverables",
    "pitch_angle",
    "personalization_facts",
)


async def apply_campaign_brief(
    db: AsyncSession,
    *,
    brand_opportunity_id: str,
    data: dict,
    evidence_signal_ids: list[str],
    confidence: float,
) -> CampaignBrief:
    """One current brief per BrandOpportunity — "Create pitch" again
    regenerates this row in place rather than accumulating duplicates (same
    upsert-by-foreign-key discipline as apply_brand_opportunity_score)."""
    field_values = {field: data[field] for field in _CAMPAIGN_BRIEF_FIELDS if field in data}

    brief = await get_campaign_brief(db, brand_opportunity_id=brand_opportunity_id)
    if brief is None:
        brief = CampaignBrief(
            id=generate_id("campaign_brief"),
            brand_opportunity_id=brand_opportunity_id,
            **field_values,
        )
        db.add(brief)
    else:
        for field, value in field_values.items():
            setattr(brief, field, value)

    brief.evidence_signal_ids = evidence_signal_ids
    brief.confidence = confidence
    await db.flush()
    return brief
