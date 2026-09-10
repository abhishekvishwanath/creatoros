"""Generic versioned-profile persistence (CLAUDE.md §15, §3.7 one source of
truth). Every creator-state entity that must never be overwritten in place —
CreatorProfile, VoiceProfile, AudienceProfile, CommercialProfile, and any
future one — shares this exact supersede-and-merge routine rather than each
domain module re-deriving its own copy. Lives outside app/domain/creator so
extension domains (e.g. app/domain/commercial, which extends Creator State
per Part II §65-67 without core depending on the extension) can import it
without creating a reverse dependency from core creator code onto them.

Structural typing only (no Protocol/bound TypeVar) since this repo doesn't
gate on strict type-checking — any SQLAlchemy model with id/creator_id/
version/is_current/confidence/evidence_ids columns works here.
"""

from typing import Optional, TypeVar

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import generate_id

VersionedProfile = TypeVar("VersionedProfile")


async def get_current_versioned_profile(
    db: AsyncSession, model_cls: type[VersionedProfile], creator_id: str
) -> Optional[VersionedProfile]:
    result = await db.execute(
        select(model_cls)
        .where(model_cls.creator_id == creator_id, model_cls.is_current.is_(True))
        .order_by(model_cls.version.desc())
    )
    return result.scalars().first()


async def apply_versioned_profile_update(
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
    current version's fields so a caller that only proposes some fields never
    has the side effect of nulling out ones it didn't touch.

    A field is treated as "not proposed" (falls back to the current value)
    when it's either absent *or* explicitly null — not every caller's prompt
    omits fields it can't infer the way positioning/voice do; the audience
    profile prompt instead always emits all keys, using null for "can't
    infer this," which would otherwise silently wipe a previously-known
    field the moment one run's evidence doesn't happen to support it. A
    manual-entry caller (e.g. the commercial profile's creator-facing form)
    that wants to actually clear a field must send an explicit non-null
    "empty" value for it (`""` or `[]`), not `null` — `null` always means
    "leave unchanged" here, never "clear".

    The old row's is_current flip is flushed separately, before the new
    row is added, so the two writes can never reach Postgres out of order
    relative to each other under the partial unique index that enforces
    "at most one is_current row per creator".
    """
    current = await get_current_versioned_profile(db, model_cls, creator_id)
    next_version = (current.version + 1) if current else 1

    if current is not None:
        current.is_current = False
        await db.flush()

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
