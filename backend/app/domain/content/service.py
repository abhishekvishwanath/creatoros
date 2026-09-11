"""Content state service (CLAUDE.md §8.3): the only path an agent's
proposed content-pipeline changes (pillars, briefs, scripts, critiques)
take into the database."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import generate_id
from app.domain.content.models import (
    CalendarEvent,
    ContentBrief,
    ContentItem,
    ContentPillar,
    ContentVersion,
    PublishedContent,
    Script,
)
from app.domain.creator.models import AudienceSegment
from app.domain.creator.service import get_weekly_capacity
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


async def list_content_derivatives(
    db: AsyncSession, *, creator_id: str, source_content_item_id: str
) -> list[ContentItem]:
    """The content tree grown from one source asset (CLAUDE.md §25) — every
    ContentItem the Repurposing Agent has produced from this source so far."""
    result = await db.execute(
        select(ContentItem)
        .where(
            ContentItem.creator_id == creator_id,
            ContentItem.source_content_item_id == source_content_item_id,
        )
        .order_by(ContentItem.created_at)
    )
    return list(result.scalars().all())


async def get_best_source_text(db: AsyncSession, *, content_item: ContentItem) -> Optional[str]:
    """The Repurposing Agent's "source truth" text (CLAUDE.md §25: every
    derivative must preserve it) — a final/critiqued script if one exists
    (it's been through the writer -> critic loop, so it's the most refined
    account of the piece), falling back to the raw ingested transcript for
    content that was never scripted in this app at all."""
    scripts = await list_scripts(db, content_item_id=content_item.id)
    for status in ("final", "critiqued", "rewritten", "draft"):
        for script in reversed(scripts):
            if script.status == status:
                return script.body
    return content_item.transcript


async def create_repurposed_content_item(
    db: AsyncSession,
    *,
    creator_id: str,
    source_item: ContentItem,
    target_platform: str,
    target_format: str,
    title: str,
    body: str,
    hook_variants: list[str],
) -> tuple[ContentItem, Script]:
    """Creates one derivative in the source asset's content tree (CLAUDE.md
    §25). Unlike create_content_item_from_opportunity's IDEA/APPROVED start,
    a derivative is born already SCRIPTED — the Repurposing Agent's job is
    specifically to adapt existing source truth into a platform-native draft
    in one step, not to re-run the from-scratch brief -> script pipeline on
    material that's already been reported and reasoned about once."""
    item = ContentItem(
        id=generate_id("content_item"),
        creator_id=creator_id,
        title=title,
        platform=target_platform,
        format=target_format,
        topic=source_item.topic,
        pillar_id=source_item.pillar_id,
        source_type="repurposed",
        source_content_item_id=source_item.id,
        status="SCRIPTED",
    )
    db.add(item)
    await db.flush()

    script = Script(
        id=generate_id("script"),
        content_item_id=item.id,
        brief_id=None,
        version_number=1,
        platform=target_platform,
        body=body,
        hook_variants=hook_variants,
        status="draft",
    )
    db.add(script)
    await db.flush()
    return item, script


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


# CLAUDE.md §26 content operations. RECORDED/EDITING are human-driven — the
# creator physically records/edits off-app, so there's nothing for an agent
# to do here beyond letting them report progress. They're deliberately
# optional rather than mandatory gates: a text post or carousel has nothing
# to "record", so scheduling is allowed straight from REVIEW too (see
# SCHEDULABLE_FROM below), not forced through both stages first.
MANUAL_STAGE_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "RECORDED": ("REVIEW",),
    "EDITING": ("RECORDED",),
}
SCHEDULABLE_FROM = ("REVIEW", "RECORDED", "EDITING")


async def mark_content_stage(db: AsyncSession, *, content_item_id: str, to_status: str) -> ContentItem:
    """Raises ValueError (caller maps to 409) rather than silently no-op'ing
    like `_advance_content_status` — this is a direct user action from a
    button click, so an invalid transition needs to surface, not vanish."""
    if to_status not in MANUAL_STAGE_TRANSITIONS:
        raise ValueError(f"{to_status!r} is not a manually-settable stage.")
    item = await db.get(ContentItem, content_item_id)
    if item is None:
        raise ValueError("Content item not found.")
    allowed_from = MANUAL_STAGE_TRANSITIONS[to_status]
    if item.status not in allowed_from:
        raise ValueError(f"Cannot mark {to_status} from status {item.status!r} (expected one of {allowed_from}).")
    item.status = to_status
    await db.flush()
    return item


async def schedule_content_item(
    db: AsyncSession, *, content_item_id: str, scheduled_at: datetime, platform: Optional[str]
) -> tuple[ContentItem, CalendarEvent]:
    item = await db.get(ContentItem, content_item_id)
    if item is None:
        raise ValueError("Content item not found.")
    if item.status not in SCHEDULABLE_FROM:
        raise ValueError(f"Cannot schedule from status {item.status!r} (expected one of {SCHEDULABLE_FROM}).")

    result = await db.execute(select(CalendarEvent).where(CalendarEvent.content_item_id == content_item_id))
    event = result.scalar_one_or_none()
    resolved_platform = platform or item.platform
    if event is None:
        event = CalendarEvent(
            id=generate_id("calendar_event"),
            creator_id=item.creator_id,
            content_item_id=content_item_id,
            scheduled_at=scheduled_at,
            platform=resolved_platform,
            status="scheduled",
        )
        db.add(event)
    else:
        event.scheduled_at = scheduled_at
        event.platform = resolved_platform
        event.status = "scheduled"

    item.status = "SCHEDULED"
    await db.flush()
    return item, event


async def publish_content_item(
    db: AsyncSession, *, content_item_id: str, url: Optional[str], external_id: Optional[str]
) -> tuple[ContentItem, PublishedContent]:
    item = await db.get(ContentItem, content_item_id)
    if item is None:
        raise ValueError("Content item not found.")
    if item.status != "SCHEDULED":
        raise ValueError(f"Cannot publish from status {item.status!r} (expected 'SCHEDULED').")

    result = await db.execute(select(CalendarEvent).where(CalendarEvent.content_item_id == content_item_id))
    event = result.scalar_one_or_none()
    platform = (event.platform if event else None) or item.platform
    if not platform:
        raise ValueError("Cannot publish: no platform is set on this content item or its calendar event.")

    published = PublishedContent(
        id=generate_id("published_content"),
        content_item_id=content_item_id,
        platform=platform,
        external_id=external_id,
        url=url,
        published_at=datetime.now(timezone.utc),
    )
    db.add(published)
    if event is not None:
        event.status = "published"
    item.status = "PUBLISHED"
    await db.flush()
    return item, published


async def list_calendar_events(
    db: AsyncSession,
    *,
    creator_id: str,
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> list[tuple[CalendarEvent, Optional[ContentItem]]]:
    query = (
        select(CalendarEvent, ContentItem)
        .outerjoin(ContentItem, ContentItem.id == CalendarEvent.content_item_id)
        .where(CalendarEvent.creator_id == creator_id)
    )
    if start is not None:
        query = query.where(CalendarEvent.scheduled_at >= start)
    if end is not None:
        query = query.where(CalendarEvent.scheduled_at <= end)
    query = query.order_by(CalendarEvent.scheduled_at)
    result = await db.execute(query)
    return [(row[0], row[1]) for row in result.all()]


async def get_content_bottlenecks(db: AsyncSession, *, creator_id: str) -> list[dict]:
    """Rule-based, evidence-grounded operational flags (CLAUDE.md §26's own
    examples: a pipeline backlog, capacity overrun). Deliberately not an
    agent call — these are plain counts over the creator's own data with no
    hallucination risk, so spending a model call would violate CLAUDE.md
    §3.3 / §53 ("don't create an agent for every tiny operation")."""
    bottlenecks: list[dict] = []

    status_rows = await db.execute(
        select(ContentItem.status, func.count(ContentItem.id))
        .where(ContentItem.creator_id == creator_id)
        .group_by(ContentItem.status)
    )
    status_counts = dict(status_rows.all())
    backlog = status_counts.get("APPROVED", 0) + status_counts.get("BRIEFED", 0)
    in_production = sum(status_counts.get(s, 0) for s in ("SCRIPTED", "RECORDED", "EDITING", "REVIEW"))
    # Threshold is deliberately simple (not itself a scored/learned model):
    # a backlog worth flagging only when there's a real, sizeable pipeline
    # stall, not every creator with 3 fresh approvals and 1 script in flight.
    if backlog >= 3 and backlog > in_production * 2:
        bottlenecks.append(
            {
                "type": "pipeline_backlog",
                "message": (
                    f"{backlog} approved idea(s) are waiting on a brief or script, but only "
                    f"{in_production} are actively moving through production."
                ),
                "evidence": {"approved_or_briefed": backlog, "in_production": in_production},
            }
        )

    now = datetime.now(timezone.utc)
    capacity = await get_weekly_capacity(db, creator_id=creator_id)
    if capacity is not None:
        week_end = now + timedelta(days=7)
        scheduled_count = await db.scalar(
            select(func.count(CalendarEvent.id)).where(
                CalendarEvent.creator_id == creator_id,
                CalendarEvent.status == "scheduled",
                CalendarEvent.scheduled_at >= now,
                CalendarEvent.scheduled_at <= week_end,
            )
        )
        scheduled_count = scheduled_count or 0
        if scheduled_count > capacity:
            bottlenecks.append(
                {
                    "type": "over_capacity",
                    "message": (
                        f"{scheduled_count} piece(s) are scheduled in the next 7 days, above your "
                        f"stated weekly capacity of {capacity}."
                    ),
                    "evidence": {"scheduled": scheduled_count, "weekly_capacity": capacity},
                }
            )

    missed_count = await db.scalar(
        select(func.count(CalendarEvent.id)).where(
            CalendarEvent.creator_id == creator_id,
            CalendarEvent.status == "scheduled",
            CalendarEvent.scheduled_at < now,
        )
    )
    if missed_count:
        bottlenecks.append(
            {
                "type": "missed_schedule",
                "message": (
                    f"{missed_count} scheduled item(s) are past their scheduled time and haven't "
                    "been marked published."
                ),
                "evidence": {"missed": missed_count},
            }
        )

    return bottlenecks
