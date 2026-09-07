from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.api.deps import DbSession, get_owned_creator
from app.domain.creator.models import (
    AudienceProfile,
    Creator,
    CreatorGoal,
    CreatorProfile,
    User,
    VoiceProfile,
)
from app.schemas.creator import (
    AudienceProfileRead,
    CreatorCreate,
    CreatorCreateResponse,
    CreatorGoalRead,
    CreatorProfileRead,
    CreatorRead,
    CreatorStateSnapshot,
    VoiceProfileRead,
)

router = APIRouter(prefix="/creators", tags=["creators"])


@router.post("", response_model=CreatorCreateResponse, status_code=201)
async def create_creator(payload: CreatorCreate, db: DbSession) -> Creator:
    """Onboarding entry point (CLAUDE.md 33 Phase 1). Finds or creates the
    owning user by email, then creates a new Creator entity under them.

    TODO(auth): once Supabase Auth is wired up, the user will already exist
    (created at signup) and this endpoint will just attach a Creator to the
    authenticated user instead of finding/creating by email.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email=payload.email)
        db.add(user)
        await db.flush()

    creator = Creator(
        user_id=user.id,
        name=payload.name,
        niche=payload.niche,
        sub_niche=payload.sub_niche,
        geography=payload.geography,
        languages=payload.languages,
        business_model=payload.business_model,
        monetization_model=payload.monetization_model,
    )
    db.add(creator)
    await db.commit()
    await db.refresh(creator)
    return creator


@router.get("/{creator_id}", response_model=CreatorRead)
async def get_creator(creator: Creator = Depends(get_owned_creator)) -> Creator:
    return creator


@router.get("/{creator_id}/state", response_model=CreatorStateSnapshot)
async def get_creator_state(db: DbSession, creator: Creator = Depends(get_owned_creator)) -> CreatorStateSnapshot:
    """Creator State Snapshot (CLAUDE.md 32): the bounded working context handed
    to an agent for a task, assembled fresh here from current state rather than
    cached — later phases add recent content / research / experiments / learnings
    once those subsystems exist."""

    profile_result = await db.execute(
        select(CreatorProfile)
        .where(CreatorProfile.creator_id == creator.id, CreatorProfile.is_current.is_(True))
        .order_by(CreatorProfile.version.desc())
    )
    profile = profile_result.scalars().first()

    voice_result = await db.execute(
        select(VoiceProfile)
        .where(VoiceProfile.creator_id == creator.id, VoiceProfile.is_current.is_(True))
        .order_by(VoiceProfile.version.desc())
    )
    voice = voice_result.scalars().first()

    audience_result = await db.execute(
        select(AudienceProfile)
        .where(AudienceProfile.creator_id == creator.id, AudienceProfile.is_current.is_(True))
        .order_by(AudienceProfile.version.desc())
    )
    audience = audience_result.scalars().first()

    goals_result = await db.execute(
        select(CreatorGoal).where(CreatorGoal.creator_id == creator.id, CreatorGoal.status == "active")
    )
    goals = list(goals_result.scalars().all())

    return CreatorStateSnapshot(
        creator=CreatorRead.model_validate(creator),
        positioning=CreatorProfileRead.model_validate(profile) if profile else None,
        voice=VoiceProfileRead.model_validate(voice) if voice else None,
        audience=AudienceProfileRead.model_validate(audience) if audience else None,
        active_goals=[CreatorGoalRead.model_validate(g) for g in goals],
    )
