"""Audience signal ingestion + Audience Intelligence Agent endpoints
(CLAUDE.md §19, §33 Phase 3).

Manual signal entry only for now — no comments/analytics API is connected
yet (see README). Mirrors app/api/routes/research.py's ingestion shape and
app/api/routes/creators.py's /analyze application-service shape: the agent
itself never touches the database directly (CLAUDE.md §8.3).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.agent_service.agents.audience_intelligence import AudienceIntelligenceAgent
from app.agent_service.context.builder import build_audience_signals_context, build_creator_state_snapshot
from app.agent_service.model_router.router import get_model_router
from app.agent_service.orchestrator.orchestrator import Orchestrator
from app.api.deps import DbSession, get_owned_creator
from app.domain.creator.models import Creator
from app.domain.creator.service import (
    apply_audience_profile_update,
    apply_audience_segments,
    get_current_audience_profile,
    ingest_audience_signal,
    list_audience_segments,
    list_audience_signals,
)
from app.schemas.creator import (
    AnalyzeAudienceResponse,
    AudienceProfileRead,
    AudienceSegmentRead,
    AudienceSignalCreate,
    AudienceSignalRead,
)

# Two routers under one file rather than one router with a concatenated
# "-signals" path: /audience-signals (plain CRUD) and /audience/analyze (the
# agent invocation) are different resource shapes that happen to share a
# word, not a nested resource — same file because they're small and tightly
# coupled, separate prefixes so neither path is built by string-pasting.
signals_router = APIRouter(prefix="/creators/{creator_id}/audience-signals", tags=["audience"])
analyze_router = APIRouter(prefix="/creators/{creator_id}/audience", tags=["audience"])


@signals_router.post("", response_model=AudienceSignalRead, status_code=201)
async def create_audience_signal(
    payload: AudienceSignalCreate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> AudienceSignalRead:
    signal = await ingest_audience_signal(db, creator_id=creator.id, data=payload.model_dump())
    await db.commit()
    await db.refresh(signal)
    return AudienceSignalRead.model_validate(signal)


@signals_router.get("", response_model=list[AudienceSignalRead])
async def get_audience_signals(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AudienceSignalRead]:
    signals = await list_audience_signals(db, creator_id=creator.id, limit=limit, offset=offset)
    return [AudienceSignalRead.model_validate(s) for s in signals]


@analyze_router.post("/analyze", response_model=AnalyzeAudienceResponse)
async def analyze_audience(db: DbSession, creator: Creator = Depends(get_owned_creator)) -> AnalyzeAudienceResponse:
    # Only the base snapshot fields the agent's prompts actually read
    # (positioning) are needed here — unlike /creators/{id}/analyze and the
    # other *.generate routes, this response doesn't need the full UI
    # snapshot afterward, so we build it once and read segments via a
    # narrow query rather than rebuilding the whole thing a second time.
    snapshot = await build_creator_state_snapshot(db, creator)
    audience_signals = await build_audience_signals_context(db, creator)

    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    agent = AudienceIntelligenceAgent()
    output = await orchestrator.run_agent(
        agent=agent,
        creator_id=creator.id,
        workflow_name="audience_intelligence",
        context=snapshot,
        audience_signals=audience_signals,
    )

    if output.status == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=output.summary + ("; " + "; ".join(output.warnings) if output.warnings else ""),
        )

    for change in output.proposed_state_changes:
        change_type = change.get("type")
        if change_type == "audience_profile_upsert":
            await apply_audience_profile_update(
                db,
                creator_id=creator.id,
                data=change["data"],
                confidence=change.get("confidence", 0.0),
                evidence_ids=change.get("evidence_ids", []),
            )
        elif change_type == "audience_segments_upsert":
            await apply_audience_segments(
                db, creator_id=creator.id, segments=change["data"].get("segments", [])
            )

    await db.commit()

    profile = await get_current_audience_profile(db, creator.id)
    segments = await list_audience_segments(db, creator_id=creator.id)
    return AnalyzeAudienceResponse(
        audience=AudienceProfileRead.model_validate(profile) if profile else None,
        segments=[AudienceSegmentRead.model_validate(s) for s in segments],
        warnings=output.warnings,
    )
