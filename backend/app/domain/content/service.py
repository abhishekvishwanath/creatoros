"""Content state service (CLAUDE.md §8.3), mirroring
app/domain/creator/service.py's role for content pillars: the only path the
Creator Intelligence Agent's pillar proposals take into the database."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import generate_id
from app.domain.content.models import ContentPillar


async def sync_content_pillars(
    db: AsyncSession, *, creator_id: str, pillars: list[dict]
) -> list[ContentPillar]:
    """Matches each proposed pillar to an existing one by name (case-
    insensitive) and updates its description, or creates a new one.

    Deliberately additive, never destructive: a pillar that doesn't appear in
    this run's proposal is left alone rather than deleted, since "the model
    didn't mention it this time" is weak evidence that a real, previously
    identified pillar has stopped existing (CLAUDE.md §15 spirit — don't
    erase state on a low-confidence signal).
    """
    result = await db.execute(select(ContentPillar).where(ContentPillar.creator_id == creator_id))
    existing_by_name = {p.name.lower(): p for p in result.scalars().all()}

    synced = []
    for proposal in pillars:
        name = proposal.get("name")
        if not name:
            continue
        existing = existing_by_name.get(name.lower())
        if existing:
            existing.description = proposal.get("description", existing.description)
            synced.append(existing)
        else:
            new_pillar = ContentPillar(
                id=generate_id("content_pillar"),
                creator_id=creator_id,
                name=name,
                description=proposal.get("description"),
            )
            db.add(new_pillar)
            synced.append(new_pillar)
            # Register immediately so a later near-duplicate name in the same
            # proposal list (e.g. a model returning both "Budgeting" and
            # "budgeting") matches this new row instead of creating a second
            # one that no future run could ever merge back together.
            existing_by_name[name.lower()] = new_pillar

    await db.flush()
    return synced
