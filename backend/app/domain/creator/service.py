"""Creator state service (CLAUDE.md §8.3): the only path an agent's proposed
changes take into the database. Agents never issue raw SQL — they return a
structured proposal, and this module is the "validator/state service" that
turns it into a properly versioned row (CLAUDE.md §15: never overwrite
important history)."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import generate_id
from app.domain.creator.models import CreatorProfile


async def get_current_creator_profile(db: AsyncSession, creator_id: str) -> Optional[CreatorProfile]:
    result = await db.execute(
        select(CreatorProfile)
        .where(CreatorProfile.creator_id == creator_id, CreatorProfile.is_current.is_(True))
        .order_by(CreatorProfile.version.desc())
    )
    return result.scalars().first()


_PROFILE_FIELDS = (
    "bio",
    "expertise",
    "positioning_statement",
    "prohibited_topics",
    "avoided_claims",
    "rejected_tones",
    "disclosure_requirements",
)


async def apply_creator_profile_update(
    db: AsyncSession,
    *,
    creator_id: str,
    data: dict,
    confidence: float,
    evidence_ids: list[str],
) -> CreatorProfile:
    """Supersedes the current CreatorProfile with a new version rather than
    mutating it in place, so a materially wrong or low-confidence update never
    silently erases the profile that produced it.

    `data` is a *partial* update: any field an agent doesn't populate (e.g.
    CreatorIntelligenceAgent never touches boundaries) carries forward from
    the current version instead of being reset to null — an agent proposing
    a better positioning statement should never have the side effect of
    wiping out boundaries a creator explicitly set.
    """
    current = await get_current_creator_profile(db, creator_id)
    next_version = (current.version + 1) if current else 1

    if current is not None:
        current.is_current = False

    merged = {
        field: data[field] if field in data else (getattr(current, field) if current else None)
        for field in _PROFILE_FIELDS
    }

    new_profile = CreatorProfile(
        id=generate_id("creator_profile"),
        creator_id=creator_id,
        version=next_version,
        is_current=True,
        confidence=confidence,
        evidence_ids=evidence_ids,
        **merged,
    )
    db.add(new_profile)
    await db.flush()
    return new_profile
