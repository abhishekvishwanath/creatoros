"""Commercial Creator DNA (CLAUDE.md §67, Part II Phase 1).

Phase 1 ships manual entry only: the creator sets their own commercial
profile directly (confidence=1.0 — their own stated facts, not an
inference). A later phase can let the Creator Intelligence Agent propose
updates through this same apply_commercial_profile_update path with lower
confidence + evidence_ids, without changing this route's shape.
"""

from fastapi import APIRouter, Depends

from app.api.deps import DbSession, get_owned_creator
from app.domain.commercial.models import CommercialProfile
from app.domain.commercial.service import apply_commercial_profile_update, get_current_commercial_profile
from app.domain.creator.models import Creator
from app.schemas.commercial import CommercialProfileRead, CommercialProfileUpdate

router = APIRouter(prefix="/creators/{creator_id}/commercial-profile", tags=["commercial"])


@router.get("", response_model=CommercialProfileRead | None)
async def get_commercial_profile(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> CommercialProfile | None:
    return await get_current_commercial_profile(db, creator_id=creator.id)


@router.put("", response_model=CommercialProfileRead)
async def update_commercial_profile(
    payload: CommercialProfileUpdate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> CommercialProfile:
    profile = await apply_commercial_profile_update(
        db, creator_id=creator.id, data=payload.model_dump(exclude_unset=True)
    )
    await db.commit()
    await db.refresh(profile)
    return profile
