"""Research signal ingestion (CLAUDE.md §17, §33 Phase 3).

Manual entry only for now — no platform/search API is connected yet (see
README). A creator or their team pastes in what they observed elsewhere: a
competitor post that took off, a trend, a recurring audience question. This
is the raw material the Opportunity Engine Agent scores against.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.agent_service.agents.trend_intelligence import TrendIntelligenceAgent
from app.agent_service.context.builder import build_creator_state_snapshot, build_trend_analysis_context
from app.agent_service.model_router.router import get_model_router
from app.agent_service.orchestrator.orchestrator import Orchestrator
from app.api.deps import DbSession, get_owned_creator
from app.domain.creator.models import Creator
from app.domain.research.service import (
    ingest_research_signal,
    list_research_signals,
    list_trend_insights,
    upsert_trend_insights,
)
from app.schemas.research import (
    AnalyzeTrendsResponse,
    ResearchSignalCreate,
    ResearchSignalRead,
    TrendInsightRead,
)

router = APIRouter(prefix="/creators/{creator_id}/research-signals", tags=["research"])
trends_router = APIRouter(prefix="/creators/{creator_id}/research/trends", tags=["research"])


@router.post("", response_model=ResearchSignalRead, status_code=201)
async def create_research_signal(
    payload: ResearchSignalCreate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> ResearchSignalRead:
    signal = await ingest_research_signal(db, creator_id=creator.id, data=payload.model_dump())
    await db.commit()
    await db.refresh(signal)
    return ResearchSignalRead.model_validate(signal)


@router.get("", response_model=list[ResearchSignalRead])
async def get_research_signals(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ResearchSignalRead]:
    signals = await list_research_signals(db, creator_id=creator.id, limit=limit, offset=offset)
    return [ResearchSignalRead.model_validate(s) for s in signals]


@trends_router.get("", response_model=list[TrendInsightRead])
async def get_trend_insights(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> list[TrendInsightRead]:
    insights = await list_trend_insights(db, creator_id=creator.id)
    return [TrendInsightRead.model_validate(i) for i in insights]


@trends_router.post("/analyze", response_model=AnalyzeTrendsResponse)
async def analyze_trends(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> AnalyzeTrendsResponse:
    """Momentum/signal counts are computed in code (CLAUDE.md §20); the
    Trend Intelligence Agent only judges saturation, durability, and
    relevance to this creator over those given numbers (CLAUDE.md §11.4)."""
    stats, prompt_topics = await build_trend_analysis_context(db, creator_id=creator.id)
    snapshot = await build_creator_state_snapshot(db, creator)

    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    output = await orchestrator.run_agent(
        agent=TrendIntelligenceAgent(),
        creator_id=creator.id,
        workflow_name="trend_analysis",
        context=snapshot,
        topics=prompt_topics,
    )

    if output.status == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=output.summary + ("; " + "; ".join(output.warnings) if output.warnings else ""),
        )

    insights_read: list[TrendInsightRead] = []
    for change in output.proposed_state_changes:
        if change.get("type") == "trend_insights":
            rows = await upsert_trend_insights(
                db, creator_id=creator.id, stats=stats, agent_insights=change["data"].get("insights", [])
            )
            insights_read = [TrendInsightRead.model_validate(r) for r in rows]

    await db.commit()
    return AnalyzeTrendsResponse(insights=insights_read, warnings=output.warnings)
