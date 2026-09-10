"""Commercial state service (CLAUDE.md §67, §8.3): the only path a
commercial-profile update takes into the database, whether it comes from the
creator directly (Phase 1: a manual form, confidence=1.0 — their own stated
facts, not an inference) or later from an agent's proposed update (Phase 3+:
lower confidence, evidence_ids attached, same shape either way).

Versioning/supersede logic is shared with CreatorProfile/VoiceProfile/
AudienceProfile via app/domain/shared/versioned_profile.py rather than
re-derived here (CLAUDE.md §3.7 one source of truth, Part II §65).
"""

from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.commercial.models import CommercialProfile
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
