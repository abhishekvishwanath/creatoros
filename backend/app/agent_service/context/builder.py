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

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.content.models import ContentItem, ContentPillar
from app.domain.creator.models import (
    AudienceProfile,
    AudienceSegment,
    AudienceSignal,
    Creator,
    CreatorGoal,
    CreatorProfile,
    VoiceProfile,
)
from app.domain.research.models import ResearchSignal, ResearchSource
from app.domain.strategy.service import list_available_opportunities
from app.schemas.creator import (
    AudienceProfileRead,
    AudienceSegmentRead,
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

    # Bounded on purpose (CLAUDE.md §10: never dump the whole database into a
    # model call) — the 10 most recent items is enough for a cold-start voice
    # read; a Script Agent's context later will want a semantically-filtered
    # slice instead of "most recent", not just a bigger number of these.
    content_result = await db.execute(
        select(ContentItem)
        .where(ContentItem.creator_id == creator.id)
        .order_by(desc(ContentItem.created_at))
        .limit(10)
    )
    recent_content = [
        {
            "id": c.id,
            "title": c.title,
            "platform": c.platform,
            "format": c.format,
            "topic": c.topic,
            "has_transcript": bool(c.transcript),
        }
        for c in content_result.scalars().all()
    ]

    pillars_result = await db.execute(select(ContentPillar).where(ContentPillar.creator_id == creator.id))
    content_pillars = [
        {"id": p.id, "name": p.name, "description": p.description} for p in pillars_result.scalars().all()
    ]

    # Bounded like recent_content above — metadata only (no summary text) so
    # the UI-facing snapshot stays small; the Opportunity Engine agent pulls
    # full signal text separately via build_research_signals_context.
    signals_result = await db.execute(
        select(ResearchSignal)
        .where(ResearchSignal.creator_id == creator.id)
        .order_by(desc(ResearchSignal.created_at))
        .limit(10)
    )
    current_research_signals = [
        {"id": s.id, "topic": s.topic, "subtopic": s.subtopic, "format": s.format}
        for s in signals_result.scalars().all()
    ]

    segments_result = await db.execute(select(AudienceSegment).where(AudienceSegment.creator_id == creator.id))
    audience_segments = [AudienceSegmentRead.model_validate(s) for s in segments_result.scalars().all()]

    return CreatorStateSnapshot(
        creator=CreatorRead.model_validate(creator),
        positioning=CreatorProfileRead.model_validate(profile) if profile else None,
        voice=VoiceProfileRead.model_validate(voice) if voice else None,
        audience=AudienceProfileRead.model_validate(audience) if audience else None,
        active_goals=[CreatorGoalRead.model_validate(g) for g in goals],
        recent_content=recent_content,
        content_pillars=content_pillars,
        current_research_signals=current_research_signals,
        audience_segments=audience_segments,
    )


VOICE_ANALYSIS_MAX_ITEMS = 5
VOICE_ANALYSIS_CHAR_LIMIT = 2000


async def build_voice_analysis_transcripts(db: AsyncSession, creator: Creator) -> list[dict]:
    """Task-specific context slice for voice AND content-pillar inference
    (CLAUDE.md §10): unlike the UI-facing snapshot above, which only carries
    content *metadata* to stay bounded, both of those sub-jobs need actual
    transcript text. Kept separate rather than added to CreatorStateSnapshot
    so the read endpoint never ships full transcript text to the browser on
    every page load — this is deliberately narrower, pulled only when an
    agent asks for it, and the same sample is reused for both sub-jobs rather
    than querying twice.

    Each item keeps its content_item id alongside the (truncated) text so the
    agent can cite exactly which content it drew a voice trait from
    (CLAUDE.md §3.4 evidence over vibes) rather than a bare unsourced claim.
    Still bounded: at most VOICE_ANALYSIS_MAX_ITEMS items, each truncated to
    VOICE_ANALYSIS_CHAR_LIMIT characters.
    """
    result = await db.execute(
        select(ContentItem)
        .where(ContentItem.creator_id == creator.id, ContentItem.transcript.isnot(None))
        .order_by(desc(ContentItem.created_at))
        .limit(VOICE_ANALYSIS_MAX_ITEMS)
    )
    return [
        {"id": c.id, "title": c.title, "transcript": c.transcript[:VOICE_ANALYSIS_CHAR_LIMIT]}
        for c in result.scalars().all()
        if c.transcript
    ]


RESEARCH_SIGNALS_CONTEXT_MAX_ITEMS = 20


async def build_research_signals_context(db: AsyncSession, creator: Creator) -> list[dict]:
    """Task-specific context slice for the Opportunity Engine Agent: unlike
    the UI-facing snapshot's current_research_signals (metadata only), this
    carries the actual observation text (`summary`) the agent reasons over,
    plus platform so it can cite where a signal came from. Bounded to the
    most recent RESEARCH_SIGNALS_CONTEXT_MAX_ITEMS (CLAUDE.md §10)."""
    result = await db.execute(
        select(ResearchSignal, ResearchSource)
        .join(ResearchSource, ResearchSignal.source_id == ResearchSource.id, isouter=True)
        .where(ResearchSignal.creator_id == creator.id)
        .order_by(desc(ResearchSignal.created_at))
        .limit(RESEARCH_SIGNALS_CONTEXT_MAX_ITEMS)
    )
    signals = []
    for signal, source in result.all():
        summary = (signal.content_features or {}).get("summary", "")
        signals.append(
            {
                "id": signal.id,
                "topic": signal.topic,
                "subtopic": signal.subtopic,
                "format": signal.format,
                "platform": source.platform if source else None,
                "summary": summary,
            }
        )
    return signals


AUDIENCE_SIGNALS_CONTEXT_MAX_ITEMS = 30
AUDIENCE_SIGNAL_CHAR_LIMIT = 1000


async def build_audience_signals_context(db: AsyncSession, creator: Creator) -> list[dict]:
    """Task-specific context slice for the Audience Intelligence Agent: the
    actual comment/question/feedback text (bounded per item, like
    build_voice_analysis_transcripts) rather than the metadata-only list a
    future audience-signals UI page would read. A higher item cap than
    voice/research (30 vs 20) since these are short quotes, not full
    transcripts or observation summaries."""
    result = await db.execute(
        select(AudienceSignal)
        .where(AudienceSignal.creator_id == creator.id)
        .order_by(desc(AudienceSignal.created_at))
        .limit(AUDIENCE_SIGNALS_CONTEXT_MAX_ITEMS)
    )
    return [
        {"id": s.id, "text": s.text[:AUDIENCE_SIGNAL_CHAR_LIMIT], "source_platform": s.source_platform}
        for s in result.scalars().all()
    ]


async def build_available_opportunities_context(db: AsyncSession, creator: Creator) -> list[dict]:
    """Task-specific context slice for the Strategy Engine Agent: opportunities
    the creator has approved or saved but not yet folded into an activated
    strategy. Delegates the actual query to
    app/domain/strategy/service.py::list_available_opportunities so the API
    layer's notion of "available" and the agent's can never drift apart —
    this just projects the same ORM rows to the plain dicts the prompt uses."""
    opportunities = await list_available_opportunities(db, creator_id=creator.id, limit=20)
    return [
        {"id": o.id, "topic": o.topic, "subtopic": o.subtopic, "format": o.format, "score": o.score}
        for o in opportunities
    ]
