"""Creator state service (CLAUDE.md §8.3): the only path an agent's proposed
changes take into the database. Agents never issue raw SQL — they return a
structured proposal, and this module is the "validator/state service" that
turns it into a properly versioned row (CLAUDE.md §15: never overwrite
important history)."""

from typing import Optional, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import generate_id
from app.domain.creator.models import CreatorProfile, VoiceProfile

VersionedProfile = TypeVar("VersionedProfile", CreatorProfile, VoiceProfile)


async def _get_current(db: AsyncSession, model_cls: type[VersionedProfile], creator_id: str) -> Optional[VersionedProfile]:
    result = await db.execute(
        select(model_cls)
        .where(model_cls.creator_id == creator_id, model_cls.is_current.is_(True))
        .order_by(model_cls.version.desc())
    )
    return result.scalars().first()


async def _apply_versioned_update(
    db: AsyncSession,
    *,
    model_cls: type[VersionedProfile],
    id_prefix: str,
    creator_id: str,
    data: dict,
    fields: tuple[str, ...],
    confidence: float,
    evidence_ids: list[str],
) -> VersionedProfile:
    """Supersedes the current row with a new version rather than mutating it
    in place (CLAUDE.md §15), merging `data` (a *partial* update) over the
    current version's fields so an agent that only proposes some fields never
    has the side effect of nulling out ones it didn't touch."""
    current = await _get_current(db, model_cls, creator_id)
    next_version = (current.version + 1) if current else 1

    if current is not None:
        current.is_current = False

    merged = {
        field: data[field] if field in data else (getattr(current, field) if current else None)
        for field in fields
    }

    new_row = model_cls(
        id=generate_id(id_prefix),
        creator_id=creator_id,
        version=next_version,
        is_current=True,
        confidence=confidence,
        evidence_ids=evidence_ids,
        **merged,
    )
    db.add(new_row)
    await db.flush()
    return new_row


async def get_current_creator_profile(db: AsyncSession, creator_id: str) -> Optional[CreatorProfile]:
    return await _get_current(db, CreatorProfile, creator_id)


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
    return await _apply_versioned_update(
        db,
        model_cls=CreatorProfile,
        id_prefix="creator_profile",
        creator_id=creator_id,
        data=data,
        fields=_PROFILE_FIELDS,
        confidence=confidence,
        evidence_ids=evidence_ids,
    )


_VOICE_FIELDS = (
    "tone",
    "vocabulary",
    "sentence_style",
    "pacing",
    "personality",
    "humor_level",
    "controversy_tolerance",
    "storytelling_style",
    "opinion_style",
    "signature_phrases",
    "cta_style",
)


async def get_current_voice_profile(db: AsyncSession, creator_id: str) -> Optional[VoiceProfile]:
    return await _get_current(db, VoiceProfile, creator_id)


async def apply_voice_profile_update(
    db: AsyncSession,
    *,
    creator_id: str,
    data: dict,
    confidence: float,
    evidence_ids: list[str],
) -> VoiceProfile:
    return await _apply_versioned_update(
        db,
        model_cls=VoiceProfile,
        id_prefix="voice_profile",
        creator_id=creator_id,
        data=data,
        fields=_VOICE_FIELDS,
        confidence=confidence,
        evidence_ids=evidence_ids,
    )
