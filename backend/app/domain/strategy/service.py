"""Strategy state service (CLAUDE.md §8.3, §21): the only path the Strategy
Engine Agent's proposals take into the database, plus the read/status paths
the API routes use.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.ids import generate_id
from app.domain.research.models import Opportunity
from app.domain.strategy.models import Strategy, StrategyItem

AVAILABLE_OPPORTUNITY_STATUSES = ("approved", "saved_for_later")


async def list_available_opportunities(db: AsyncSession, *, creator_id: str, limit: int = 20) -> list[Opportunity]:
    """Opportunities a strategy can still be built from: approved or saved,
    not yet folded into an activated strategy (CLAUDE.md §21 — a strategy
    consumes opportunities, it doesn't keep proposing the same ones)."""
    result = await db.execute(
        select(Opportunity)
        .where(Opportunity.creator_id == creator_id, Opportunity.status.in_(AVAILABLE_OPPORTUNITY_STATUSES))
        .order_by(desc(Opportunity.score))
        .limit(limit)
    )
    return list(result.scalars().all())


async def apply_strategy(
    db: AsyncSession, *, creator_id: str, summary: str, confidence: float, items: list[dict]
) -> Strategy:
    """Inserts a new draft Strategy with its items. Additive like
    Opportunity generation (app/domain/research/service.py) rather than
    versioned — each generation run is a fresh proposal the creator reviews
    and activates, not a merge into a prior plan."""
    # ISO week (Monday..Sunday) containing today — day_of_week on each item
    # (0=Mon..6=Sun) maps onto this concrete window.
    today = datetime.now(timezone.utc).date()
    period_start = today - timedelta(days=today.weekday())
    period_end = period_start + timedelta(days=6)

    strategy = Strategy(
        id=generate_id("strategy"),
        creator_id=creator_id,
        period_start=period_start,
        period_end=period_end,
        summary=summary,
        status="draft",
        confidence=confidence,
    )
    for item in items:
        strategy.items.append(
            StrategyItem(
                id=generate_id("strategy_item"),
                opportunity_id=item.get("opportunity_id"),
                day_of_week=item.get("day_of_week"),
                portfolio_role=item.get("portfolio_role"),
                status="planned",
            )
        )
    db.add(strategy)
    await db.flush()
    return strategy


def _item_query():
    return select(Strategy).options(selectinload(Strategy.items).selectinload(StrategyItem.opportunity))


async def get_strategy(db: AsyncSession, *, creator_id: str, strategy_id: str) -> Optional[Strategy]:
    result = await db.execute(
        _item_query().where(Strategy.id == strategy_id, Strategy.creator_id == creator_id)
    )
    return result.scalar_one_or_none()


async def list_strategies(db: AsyncSession, *, creator_id: str, limit: int = 20, offset: int = 0) -> list[Strategy]:
    result = await db.execute(
        _item_query()
        .where(Strategy.creator_id == creator_id)
        .order_by(desc(Strategy.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


async def update_strategy_status(
    db: AsyncSession, *, creator_id: str, strategy_id: str, status: str
) -> Optional[Strategy]:
    """Activating a strategy marks the opportunities it consumed as "used"
    (CLAUDE.md §20 status lifecycle) so they stop showing up as available for
    the *next* strategy generation — a draft that's never activated leaves
    its opportunities untouched and reusable."""
    strategy = await get_strategy(db, creator_id=creator_id, strategy_id=strategy_id)
    if strategy is None:
        return None

    strategy.status = status

    if status == "active":
        opportunity_ids = [item.opportunity_id for item in strategy.items if item.opportunity_id]
        if opportunity_ids:
            result = await db.execute(
                select(Opportunity).where(Opportunity.id.in_(opportunity_ids), Opportunity.creator_id == creator_id)
            )
            for opportunity in result.scalars().all():
                opportunity.status = "used"

    await db.flush()
    return strategy
