"""Context Builder (CLAUDE.md §10, §32): assembles the bounded, task-specific
working context handed to an agent. Never dump the whole database into a model
call — retrieve only what's relevant, and keep it traceable.

Currently this produces one shape (the Creator State Snapshot) reused by both
the `/creators/{id}/state` read endpoint and every agent invocation, so the UI
and the agents are always looking at the same picture of the creator. As more
subsystems land (content, research, performance, learnings), this is where
their task-specific slices get assembled — e.g. a Script Agent's context adds
recent successful scripts and audience segment detail on top of this base,
rather than every agent reaching into the ORM directly.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.creator.models import (
    AudienceProfile,
    Creator,
    CreatorGoal,
    CreatorProfile,
    VoiceProfile,
)
from app.schemas.creator import (
    AudienceProfileRead,
    CreatorGoalRead,
    CreatorProfileRead,
    CreatorRead,
    CreatorStateSnapshot,
    VoiceProfileRead,
)


async def build_creator_state_snapshot(db: AsyncSession, creator: Creator) -> CreatorStateSnapshot:
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
