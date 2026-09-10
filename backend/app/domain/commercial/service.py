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
from app.domain.commercial.models import Brand, BrandContact, BrandSignal, CommercialProfile
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
