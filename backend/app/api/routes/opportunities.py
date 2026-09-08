"""Opportunity Engine endpoints (CLAUDE.md §20, §33 Phase 3).

Mirrors the shape of app/api/routes/creators.py's /analyze: this is the
application-service layer that invokes the Opportunity Engine Agent, then
applies whatever it proposes through the domain state service — the agent
itself never touches the database directly (CLAUDE.md §8.3).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.agent_service.agents.opportunity_engine import OpportunityEngineAgent
from app.agent_service.context.builder import build_creator_state_snapshot, build_research_signals_context
from app.agent_service.model_router.router import get_model_router
from app.agent_service.orchestrator.orchestrator import Orchestrator
from app.api.deps import DbSession, get_owned_creator
from app.domain.creator.models import Creator
from app.domain.research.service import apply_opportunities, list_opportunities, update_opportunity_status
from app.schemas.research import GenerateOpportunitiesResponse, OpportunityRead, OpportunityStatusUpdate

router = APIRouter(prefix="/creators/{creator_id}/opportunities", tags=["opportunities"])


@router.post("/generate", response_model=GenerateOpportunitiesResponse)
async def generate_opportunities(
    db: DbSession, creator: Creator = Depends(get_owned_creator)
) -> GenerateOpportunitiesResponse:
    snapshot = await build_creator_state_snapshot(db, creator)
    research_signals = await build_research_signals_context(db, creator)

    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    agent = OpportunityEngineAgent()
    output = await orchestrator.run_agent(
        agent=agent,
        creator_id=creator.id,
        workflow_name="opportunity_generation",
        context=snapshot,
        research_signals=research_signals,
    )

    if output.status == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=output.summary + ("; " + "; ".join(output.warnings) if output.warnings else ""),
        )

    created = []
    for change in output.proposed_state_changes:
        if change.get("type") == "opportunities_upsert":
            created = await apply_opportunities(
                db, creator_id=creator.id, opportunities=change["data"].get("opportunities", [])
            )

    await db.commit()
    return GenerateOpportunitiesResponse(
        opportunities=[OpportunityRead.model_validate(o) for o in created],
        warnings=output.warnings,
    )


@router.get("", response_model=list[OpportunityRead])
async def get_opportunities(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
    status_filter: str | None = Query(default=None, alias="status"),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[OpportunityRead]:
    opportunities = await list_opportunities(
        db, creator_id=creator.id, status=status_filter, limit=limit, offset=offset
    )
    return [OpportunityRead.model_validate(o) for o in opportunities]


@router.patch("/{opportunity_id}", response_model=OpportunityRead)
async def patch_opportunity_status(
    opportunity_id: str,
    payload: OpportunityStatusUpdate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> OpportunityRead:
    opportunity = await update_opportunity_status(
        db, creator_id=creator.id, opportunity_id=opportunity_id, status=payload.status
    )
    if opportunity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    await db.commit()
    return OpportunityRead.model_validate(opportunity)
