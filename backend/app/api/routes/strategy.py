"""Strategy Engine endpoints (CLAUDE.md §21, §33 Phase 4).

Mirrors app/api/routes/opportunities.py's shape: invokes the Strategy Engine
Agent, then applies whatever it proposes through the domain state service —
the agent itself never touches the database directly (CLAUDE.md §8.3).
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.agent_service.agents.strategy_engine import StrategyEngineAgent
from app.agent_service.context.builder import build_available_opportunities_context, build_creator_state_snapshot
from app.agent_service.model_router.router import get_model_router
from app.agent_service.orchestrator.orchestrator import Orchestrator
from app.api.deps import DbSession, get_owned_creator
from app.domain.creator.models import Creator
from app.domain.strategy.models import Strategy
from app.domain.strategy.service import apply_strategy, get_strategy, list_strategies, update_strategy_status
from app.schemas.strategy import GenerateStrategyResponse, StrategyItemRead, StrategyRead, StrategyStatusUpdate

router = APIRouter(prefix="/creators/{creator_id}/strategy", tags=["strategy"])


def _to_read(strategy: Strategy) -> StrategyRead:
    """Manual conversion (not StrategyRead.model_validate) because
    opportunity_topic is denormalized from the eager-loaded
    StrategyItem.opportunity relationship, not a plain column."""
    return StrategyRead(
        id=strategy.id,
        period_start=strategy.period_start,
        period_end=strategy.period_end,
        summary=strategy.summary,
        status=strategy.status,
        confidence=strategy.confidence,
        created_at=strategy.created_at,
        items=[
            StrategyItemRead(
                id=item.id,
                opportunity_id=item.opportunity_id,
                opportunity_topic=item.opportunity.topic if item.opportunity else None,
                day_of_week=item.day_of_week,
                portfolio_role=item.portfolio_role,
                status=item.status,
            )
            for item in strategy.items
        ],
    )


@router.post("/generate", response_model=GenerateStrategyResponse)
async def generate_strategy(db: DbSession, creator: Creator = Depends(get_owned_creator)) -> GenerateStrategyResponse:
    snapshot = await build_creator_state_snapshot(db, creator)
    available_opportunities = await build_available_opportunities_context(db, creator)

    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    agent = StrategyEngineAgent()
    output = await orchestrator.run_agent(
        agent=agent,
        creator_id=creator.id,
        workflow_name="strategy_generation",
        context=snapshot,
        available_opportunities=available_opportunities,
    )

    if output.status == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=output.summary + ("; " + "; ".join(output.warnings) if output.warnings else ""),
        )

    strategy_id = None
    for change in output.proposed_state_changes:
        if change.get("type") == "strategy_upsert":
            data = change["data"]
            created = await apply_strategy(
                db,
                creator_id=creator.id,
                summary=data.get("summary", ""),
                confidence=change.get("confidence", 0.0),
                items=data.get("items", []),
            )
            strategy_id = created.id

    await db.commit()

    strategy_read = None
    if strategy_id:
        # Re-fetched (not the in-memory object apply_strategy returned) so
        # StrategyItem.opportunity is eager-loaded before _to_read reads it —
        # the freshly-created items only carry opportunity_id, not the
        # relationship, and accessing it lazily here would need a second
        # await this synchronous conversion can't do.
        strategy = await get_strategy(db, creator_id=creator.id, strategy_id=strategy_id)
        strategy_read = _to_read(strategy) if strategy else None

    return GenerateStrategyResponse(strategy=strategy_read, warnings=output.warnings)


@router.get("", response_model=list[StrategyRead])
async def get_strategies(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[StrategyRead]:
    strategies = await list_strategies(db, creator_id=creator.id, limit=limit, offset=offset)
    return [_to_read(s) for s in strategies]


@router.patch("/{strategy_id}", response_model=StrategyRead)
async def patch_strategy_status(
    strategy_id: str,
    payload: StrategyStatusUpdate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> StrategyRead:
    strategy = await update_strategy_status(
        db, creator_id=creator.id, strategy_id=strategy_id, status=payload.status
    )
    if strategy is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Strategy not found")
    await db.commit()
    # update_strategy_status's own get_strategy() already eager-loaded items
    # + opportunities before we mutated statuses in place, so no re-fetch
    # needed here (unlike generate_strategy above).
    return _to_read(strategy)
