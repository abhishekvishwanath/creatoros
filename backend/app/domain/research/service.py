"""Research + Opportunity state service (CLAUDE.md §8.3): the only path a
manual research-signal submission or the Opportunity Engine Agent's proposals
take into the database.
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.ids import generate_id
from app.domain.content.models import ContentPillar
from app.domain.creator.models import CreatorPreference
from app.domain.research.models import Opportunity, OpportunityEvidence, ResearchSignal, ResearchSource


async def ingest_research_signal(db: AsyncSession, *, creator_id: str, data: dict) -> ResearchSignal:
    """Creates a ResearchSource (provenance record) when source details are
    given, then a ResearchSignal linked to it. `evidence_quality` is
    "medium" rather than "high": this is a real human-observed signal, just
    not one machine-verified against the platform itself (CLAUDE.md §16)."""
    source_id: Optional[str] = None
    if data.get("platform") or data.get("source_url") or data.get("source_title"):
        source = ResearchSource(
            id=generate_id("research_source"),
            platform=data.get("platform"),
            url=data.get("source_url"),
            source_title=data.get("source_title"),
            source_type="creator_provided",
            evidence_quality="medium",
            retrieved_at=datetime.now(timezone.utc),
        )
        db.add(source)
        await db.flush()
        source_id = source.id

    signal = ResearchSignal(
        id=generate_id("research_signal"),
        creator_id=creator_id,
        source_id=source_id,
        topic=data["topic"],
        subtopic=data.get("subtopic"),
        format=data.get("format"),
        engagement=data.get("engagement"),
        content_features={"summary": data["summary"]},
        evidence_quality="medium",
    )
    db.add(signal)
    await db.flush()
    return signal


async def list_research_signals(db: AsyncSession, *, creator_id: str, limit: int = 50, offset: int = 0) -> list[ResearchSignal]:
    result = await db.execute(
        select(ResearchSignal)
        .where(ResearchSignal.creator_id == creator_id)
        .order_by(desc(ResearchSignal.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def apply_opportunities(db: AsyncSession, *, creator_id: str, opportunities: list[dict]) -> list[Opportunity]:
    """Inserts each proposed opportunity as a new row. Unlike content pillars,
    opportunities are not a stable named identity to merge into — each
    generation run is a fresh, time-windowed read of "what's worth making
    right now", so this is purely additive with no matching-by-name step."""
    pillars_result = await db.execute(select(ContentPillar).where(ContentPillar.creator_id == creator_id))
    pillar_by_name = {p.name.lower(): p.id for p in pillars_result.scalars().all()}

    created: list[Opportunity] = []
    for proposal in opportunities:
        components = proposal.get("score_components") or {}
        score = proposal.get("score")
        if score is None and components:
            score = round(sum(components.values()) / len(components), 3)

        pillar_name = (proposal.get("content_pillar_name") or "").lower()

        opportunity = Opportunity(
            id=generate_id("opportunity"),
            creator_id=creator_id,
            topic=proposal.get("topic"),
            subtopic=proposal.get("subtopic"),
            angle=proposal.get("angle"),
            format=proposal.get("format"),
            content_pillar_id=pillar_by_name.get(pillar_name),
            strategic_goal=proposal.get("strategic_goal"),
            score=score,
            score_components=components or None,
            competition_level=proposal.get("competition_level"),
            saturation_estimate=proposal.get("saturation_estimate"),
            production_complexity=proposal.get("production_complexity"),
            recommended_time_window=proposal.get("recommended_time_window"),
            confidence=proposal.get("confidence"),
            status="pending",
        )
        for signal_id in proposal.get("evidence_signal_ids", []):
            # Appended to the relationship (not set via opportunity_id
            # directly) so opportunity.evidence is already populated in
            # memory for the caller to serialize, without a re-fetch.
            opportunity.evidence.append(
                OpportunityEvidence(
                    id=generate_id("opportunity_evidence"),
                    research_signal_id=signal_id,
                )
            )

        db.add(opportunity)
        await db.flush()
        created.append(opportunity)

    return created


async def list_opportunities(
    db: AsyncSession, *, creator_id: str, status: Optional[str] = None, limit: int = 50, offset: int = 0
) -> list[Opportunity]:
    query = (
        select(Opportunity)
        .where(Opportunity.creator_id == creator_id)
        .options(selectinload(Opportunity.evidence))
        # nulls_last: an unscored opportunity (e.g. from a malformed proposal
        # with no score_components) must never outrank a genuinely scored one
        # just because Postgres's default DESC ordering puts NULL first.
        .order_by(Opportunity.score.desc().nulls_last(), desc(Opportunity.created_at))
        .limit(limit)
        .offset(offset)
    )
    if status:
        query = query.where(Opportunity.status == status)
    result = await db.execute(query)
    return list(result.scalars().all())


async def update_opportunity_status(
    db: AsyncSession, *, creator_id: str, opportunity_id: str, status: str
) -> Optional[Opportunity]:
    """Applies a creator's decision on an opportunity and records it as an
    inferred preference signal (CLAUDE.md §33 Phase 5: "these actions should
    themselves become useful preference signals") — the foundation a future
    learning loop reads from, not itself a learning agent."""
    result = await db.execute(
        select(Opportunity)
        .where(Opportunity.id == opportunity_id, Opportunity.creator_id == creator_id)
        .options(selectinload(Opportunity.evidence))
    )
    opportunity = result.scalar_one_or_none()
    if opportunity is None:
        return None

    opportunity.status = status

    if status in ("approved", "rejected"):
        db.add(
            CreatorPreference(
                id=generate_id("creator_preference"),
                creator_id=creator_id,
                key="opportunity_feedback",
                value={
                    "opportunity_id": opportunity.id,
                    "topic": opportunity.topic,
                    "format": opportunity.format,
                    "decision": status,
                },
                source="inferred",
            )
        )

    await db.flush()
    return opportunity
