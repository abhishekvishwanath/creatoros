"""Creator state service (CLAUDE.md §8.3): the only path an agent's proposed
changes take into the database. Agents never issue raw SQL — they return a
structured proposal, and this module is the "validator/state service" that
turns it into a properly versioned row (CLAUDE.md §15: never overwrite
important history)."""

from typing import Optional, TypeVar

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import generate_id
from app.domain.creator.models import (
    AudienceProfile,
    AudienceSegment,
    AudienceSignal,
    CreatorProfile,
    VoiceProfile,
)

VersionedProfile = TypeVar("VersionedProfile", CreatorProfile, VoiceProfile, AudienceProfile)


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
    sample_size: Optional[int] = None,
) -> VersionedProfile:
    """Supersedes the current row with a new version rather than mutating it
    in place (CLAUDE.md §15), merging `data` (a *partial* update) over the
    current version's fields so an agent that only proposes some fields never
    has the side effect of nulling out ones it didn't touch.

    A field is treated as "not proposed" (falls back to the current value)
    when it's either absent *or* explicitly null — not every caller's prompt
    omits fields it can't infer the way positioning/voice do; the audience
    profile prompt instead always emits all keys, using null for "can't
    infer this," which would otherwise silently wipe a previously-known
    field the moment one run's evidence doesn't happen to support it.
    """
    current = await _get_current(db, model_cls, creator_id)
    next_version = (current.version + 1) if current else 1

    if current is not None:
        current.is_current = False

    merged = {
        field: data[field] if data.get(field) is not None else (getattr(current, field) if current else None)
        for field in fields
    }

    new_row = model_cls(
        id=generate_id(id_prefix),
        creator_id=creator_id,
        version=next_version,
        is_current=True,
        confidence=confidence,
        evidence_ids=evidence_ids,
        **({"sample_size": sample_size} if sample_size is not None else {}),
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


_AUDIENCE_PROFILE_FIELDS = (
    "geography",
    "demographics",
    "psychographics",
    "knowledge_level",
    "purchase_intent",
    "preferred_language",
)


async def get_current_audience_profile(db: AsyncSession, creator_id: str) -> Optional[AudienceProfile]:
    return await _get_current(db, AudienceProfile, creator_id)


async def apply_audience_profile_update(
    db: AsyncSession,
    *,
    creator_id: str,
    data: dict,
    confidence: float,
    evidence_ids: list[str],
) -> AudienceProfile:
    return await _apply_versioned_update(
        db,
        model_cls=AudienceProfile,
        id_prefix="audience_profile",
        creator_id=creator_id,
        data=data,
        fields=_AUDIENCE_PROFILE_FIELDS,
        confidence=confidence,
        evidence_ids=evidence_ids,
        # Unlike CreatorProfile/VoiceProfile (no such column), AudienceProfile
        # tracks how many signals informed it — same provenance AudienceSegment
        # already records via its own sample_size.
        sample_size=len(evidence_ids),
    )


_SEGMENT_FIELDS = (
    "problems",
    "desires",
    "objections",
    "questions",
    "fears",
    "aspirations",
    "language",
    "knowledge_level",
)


async def apply_audience_segments(
    db: AsyncSession, *, creator_id: str, segments: list[dict]
) -> list[AudienceSegment]:
    """Matches each proposed segment to an existing one by name (case-
    insensitive) and overwrites its fields with the latest read, or creates
    a new one — same additive-by-name pattern as
    app/domain/content/service.py::sync_content_pillars: a segment absent
    from this run's proposal is left alone rather than deleted (CLAUDE.md
    §15 spirit — don't erase state on a low-confidence signal)."""
    result = await db.execute(select(AudienceSegment).where(AudienceSegment.creator_id == creator_id))
    existing_by_name = {s.name.lower(): s for s in result.scalars().all()}

    synced = []
    for proposal in segments:
        name = proposal.get("name")
        if not name:
            continue
        confidence = proposal.get("confidence", 0.0)
        evidence_ids = proposal.get("evidence_ids", [])
        # Computed once, applied identically to both branches below — a
        # segment re-analyzed with genuinely zero cited signals should show
        # sample_size 0, not silently keep whatever the last run recorded
        # (the previous `len(evidence_ids) or existing.sample_size` treated
        # a real zero the same as "not provided").
        field_updates = {field: proposal[field] for field in _SEGMENT_FIELDS if field in proposal}
        existing = existing_by_name.get(name.lower())
        if existing:
            for field, value in field_updates.items():
                setattr(existing, field, value)
            existing.confidence = confidence
            existing.sample_size = len(evidence_ids)
            existing.evidence_ids = evidence_ids
            synced.append(existing)
        else:
            new_segment = AudienceSegment(
                id=generate_id("audience_segment"),
                creator_id=creator_id,
                name=name,
                confidence=confidence,
                sample_size=len(evidence_ids),
                evidence_ids=evidence_ids,
                **field_updates,
            )
            db.add(new_segment)
            synced.append(new_segment)
            existing_by_name[name.lower()] = new_segment

    await db.flush()
    return synced


async def list_audience_segments(db: AsyncSession, *, creator_id: str) -> list[AudienceSegment]:
    result = await db.execute(select(AudienceSegment).where(AudienceSegment.creator_id == creator_id))
    return list(result.scalars().all())


async def ingest_audience_signal(db: AsyncSession, *, creator_id: str, data: dict) -> AudienceSignal:
    signal = AudienceSignal(
        id=generate_id("audience_signal"),
        creator_id=creator_id,
        text=data["text"],
        source_platform=data.get("source_platform"),
    )
    db.add(signal)
    await db.flush()
    return signal


async def list_audience_signals(
    db: AsyncSession, *, creator_id: str, limit: int = 50, offset: int = 0
) -> list[AudienceSignal]:
    result = await db.execute(
        select(AudienceSignal)
        .where(AudienceSignal.creator_id == creator_id)
        .order_by(desc(AudienceSignal.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
