"""Content state service (CLAUDE.md §8.3): the only path an agent's
proposed content-pipeline changes (pillars, briefs, scripts, critiques)
take into the database."""

from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import generate_id
from app.domain.content.models import ContentBrief, ContentItem, ContentPillar, ContentVersion, Script
from app.domain.creator.models import AudienceSegment
from app.domain.research.models import Opportunity
from app.domain.strategy.service import AVAILABLE_OPPORTUNITY_STATUSES


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


_BRIEF_FIELDS = (
    "objective",
    "core_insight",
    "angle",
    "hook_type",
    "hook",
    "narrative_structure",
    "key_points",
    "examples",
    "broll_suggestions",
    "on_screen_text",
    "pacing",
    "cta",
    "caption_concept",
    "cover_concept",
    "repurposing_opportunities",
    "risk_notes",
)


async def create_content_item_from_opportunity(
    db: AsyncSession, *, creator_id: str, opportunity_id: str
) -> Optional[ContentItem]:
    """Entry point into the Create pipeline (CLAUDE.md §33 Phase 6): promotes
    an opportunity the creator has already approved/saved into a concrete
    content item the Content Architect Agent can then brief.

    Requires the opportunity to still be in an available status (not
    already 'used', 'rejected', or 'pending') — this doesn't close the race
    between two truly concurrent requests (both could still read the same
    pre-commit status), but it does stop the far more common case of
    promoting the same opportunity twice sequentially or after it's already
    been consumed elsewhere.
    """
    result = await db.execute(
        select(Opportunity).where(
            Opportunity.id == opportunity_id,
            Opportunity.creator_id == creator_id,
            Opportunity.status.in_(AVAILABLE_OPPORTUNITY_STATUSES),
        )
    )
    opportunity = result.scalar_one_or_none()
    if opportunity is None:
        return None

    item = ContentItem(
        id=generate_id("content_item"),
        creator_id=creator_id,
        title=opportunity.topic,
        format=opportunity.format,
        topic=opportunity.topic,
        pillar_id=opportunity.content_pillar_id,
        opportunity_id=opportunity.id,
        source_type="created",
        status="APPROVED",
    )
    db.add(item)
    # Mirrors Strategy activation (app/domain/strategy/service.py's
    # update_strategy_status): once an opportunity has been acted on, it
    # must stop showing up as "available" for future opportunity/strategy
    # generation — otherwise the same opportunity could be promoted into
    # multiple content items indefinitely.
    opportunity.status = "used"
    await db.flush()
    return item


async def get_content_item(db: AsyncSession, *, creator_id: str, content_item_id: str) -> Optional[ContentItem]:
    result = await db.execute(
        select(ContentItem).where(ContentItem.id == content_item_id, ContentItem.creator_id == creator_id)
    )
    return result.scalar_one_or_none()


async def get_content_brief(db: AsyncSession, *, content_item_id: str) -> Optional[ContentBrief]:
    result = await db.execute(select(ContentBrief).where(ContentBrief.content_item_id == content_item_id))
    return result.scalar_one_or_none()


async def list_scripts(db: AsyncSession, *, content_item_id: str) -> list[Script]:
    result = await db.execute(
        select(Script).where(Script.content_item_id == content_item_id).order_by(Script.version_number)
    )
    return list(result.scalars().all())


async def get_script(db: AsyncSession, *, content_item_id: str, script_id: str) -> Optional[Script]:
    result = await db.execute(
        select(Script).where(Script.id == script_id, Script.content_item_id == content_item_id)
    )
    return result.scalar_one_or_none()


async def _advance_content_status(db: AsyncSession, *, content_item_id: str, from_any: tuple[str, ...], to: str) -> None:
    """Shared by every pipeline stage that moves a content item forward in
    CLAUDE.md §26's state machine — a single place to change if that machine
    changes, and `db.get` instead of a fresh `select()` since every caller
    already knows the exact primary key."""
    item = await db.get(ContentItem, content_item_id)
    if item is not None and item.status in from_any:
        item.status = to


async def apply_content_brief(
    db: AsyncSession, *, creator_id: str, content_item_id: str, data: dict, evidence_ids: list[str]
) -> ContentBrief:
    """One *current* brief per content item (the model has no version/
    is_current columns, unlike CreatorProfile/VoiceProfile) — a regenerate
    updates this row in place for easy joins, but every version is also
    preserved as an immutable ContentVersion row (CLAUDE.md §15: "Version...
    briefs... The current version is a state, but previous versions remain
    inspectable") so a regenerated angle/hook/CTA isn't lost with no way to
    compare or revert.
    """
    existing = await get_content_brief(db, content_item_id=content_item_id)
    field_values = {field: data[field] for field in _BRIEF_FIELDS if field in data}

    audience_segment_id = None
    segment_name = (data.get("audience_segment_name") or "").lower()
    if segment_name:
        result = await db.execute(
            select(AudienceSegment).where(
                AudienceSegment.creator_id == creator_id, func.lower(AudienceSegment.name) == segment_name
            )
        )
        segment = result.scalar_one_or_none()
        audience_segment_id = segment.id if segment else None

    if existing:
        for field, value in field_values.items():
            setattr(existing, field, value)
        existing.evidence_ids = evidence_ids
        existing.audience_segment_id = audience_segment_id
        brief = existing
    else:
        brief = ContentBrief(
            id=generate_id("content_brief"),
            content_item_id=content_item_id,
            evidence_ids=evidence_ids,
            audience_segment_id=audience_segment_id,
            **field_values,
        )
        db.add(brief)

    prior_versions = await db.scalar(
        select(func.count(ContentVersion.id)).where(
            ContentVersion.content_item_id == content_item_id, ContentVersion.stage == "brief"
        )
    )
    db.add(
        ContentVersion(
            id=generate_id("content_version"),
            content_item_id=content_item_id,
            version_number=(prior_versions or 0) + 1,
            stage="brief",
            body={**field_values, "evidence_ids": evidence_ids, "audience_segment_name": data.get("audience_segment_name")},
            created_by="agent",
        )
    )

    await _advance_content_status(db, content_item_id=content_item_id, from_any=("APPROVED",), to="BRIEFED")
    await db.flush()
    return brief


async def create_script(
    db: AsyncSession,
    *,
    content_item_id: str,
    brief_id: str,
    platform: Optional[str],
    body: str,
    hook_variants: list[str],
    status: str = "draft",
) -> Script:
    max_version = await db.scalar(
        select(func.max(Script.version_number)).where(Script.content_item_id == content_item_id)
    )
    script = Script(
        id=generate_id("script"),
        content_item_id=content_item_id,
        brief_id=brief_id,
        version_number=(max_version or 0) + 1,
        platform=platform,
        body=body,
        hook_variants=hook_variants,
        status=status,
    )
    db.add(script)

    await _advance_content_status(
        db, content_item_id=content_item_id, from_any=("APPROVED", "BRIEFED"), to="SCRIPTED"
    )
    await db.flush()
    return script


async def apply_critique(
    db: AsyncSession, *, script: Script, critic_score: int, critic_issues: list[dict], passed: bool
) -> Script:
    script.critic_score = critic_score
    script.critic_issues = critic_issues
    script.status = "final" if passed else "critiqued"

    if passed:
        await _advance_content_status(
            db, content_item_id=script.content_item_id, from_any=("SCRIPTED", "BRIEFED"), to="REVIEW"
        )

    await db.flush()
    return script
