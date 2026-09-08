from sqlalchemy import select

from app.domain.creator.models import Creator, User
from app.domain.research.models import Opportunity
from app.domain.strategy.models import Strategy, StrategyItem
from app.domain.strategy.service import (
    apply_strategy,
    get_strategy,
    list_available_opportunities,
    list_strategies,
    update_strategy_status,
)
from app.infrastructure.db.session import AsyncSessionLocal


_creator_counter = 0


async def _make_creator() -> str:
    global _creator_counter
    _creator_counter += 1
    async with AsyncSessionLocal() as session:
        user = User(email=f"strategytest{_creator_counter}@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Strategy Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def _make_opportunity(creator_id: str, opp_id: str, status: str = "approved") -> None:
    async with AsyncSessionLocal() as session:
        session.add(Opportunity(id=opp_id, creator_id=creator_id, topic="budgeting", status=status))
        await session.commit()


async def test_list_available_opportunities_excludes_pending_and_used():
    creator_id = await _make_creator()
    await _make_opportunity(creator_id, "opp_pending", status="pending")
    await _make_opportunity(creator_id, "opp_approved", status="approved")
    await _make_opportunity(creator_id, "opp_saved", status="saved_for_later")
    await _make_opportunity(creator_id, "opp_used", status="used")

    async with AsyncSessionLocal() as session:
        available = await list_available_opportunities(session, creator_id=creator_id)

    assert {o.id for o in available} == {"opp_approved", "opp_saved"}


async def test_apply_strategy_creates_strategy_with_items_as_draft():
    creator_id = await _make_creator()
    await _make_opportunity(creator_id, "opp_1")

    async with AsyncSessionLocal() as session:
        strategy = await apply_strategy(
            session,
            creator_id=creator_id,
            summary="A balanced week.",
            confidence=0.5,
            items=[{"opportunity_id": "opp_1", "day_of_week": 0, "portfolio_role": "authority"}],
        )
        await session.commit()
        strategy_id = strategy.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Strategy).where(Strategy.id == strategy_id))
        fetched = result.scalar_one()
        items_result = await session.execute(select(StrategyItem).where(StrategyItem.strategy_id == strategy_id))
        items = items_result.scalars().all()

    assert fetched.status == "draft"
    assert fetched.confidence == 0.5
    assert fetched.period_start is not None and fetched.period_end is not None
    assert fetched.period_end > fetched.period_start
    assert len(items) == 1
    assert items[0].portfolio_role == "authority"


async def test_activating_a_strategy_marks_its_opportunities_used():
    creator_id = await _make_creator()
    await _make_opportunity(creator_id, "opp_1")

    async with AsyncSessionLocal() as session:
        strategy = await apply_strategy(
            session,
            creator_id=creator_id,
            summary="s",
            confidence=0.5,
            items=[{"opportunity_id": "opp_1", "day_of_week": 0, "portfolio_role": "reach"}],
        )
        await session.commit()
        strategy_id = strategy.id

    async with AsyncSessionLocal() as session:
        await update_strategy_status(session, creator_id=creator_id, strategy_id=strategy_id, status="active")
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Opportunity).where(Opportunity.id == "opp_1"))
        opportunity = result.scalar_one()
    assert opportunity.status == "used"


async def test_activating_a_strategy_does_not_touch_other_creators_opportunities():
    """Regression guard: the bulk opportunity update in update_strategy_status
    filters by creator_id, not just id, even though opportunity ids are
    already scoped via the strategy that owns them."""
    creator_id = await _make_creator()
    other_creator_id = await _make_creator()
    await _make_opportunity(other_creator_id, "opp_other")
    await _make_opportunity(creator_id, "opp_mine")

    async with AsyncSessionLocal() as session:
        strategy = await apply_strategy(
            session,
            creator_id=creator_id,
            summary="s",
            confidence=0.5,
            items=[{"opportunity_id": "opp_mine", "day_of_week": 0, "portfolio_role": "reach"}],
        )
        await session.commit()
        strategy_id = strategy.id

    async with AsyncSessionLocal() as session:
        await update_strategy_status(session, creator_id=creator_id, strategy_id=strategy_id, status="active")
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Opportunity).where(Opportunity.id == "opp_other"))
        other = result.scalar_one()
    assert other.status == "approved"


async def test_get_strategy_enforces_creator_scoping():
    creator_id = await _make_creator()
    other_creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        strategy = await apply_strategy(session, creator_id=creator_id, summary="s", confidence=0.5, items=[])
        await session.commit()
        strategy_id = strategy.id

    async with AsyncSessionLocal() as session:
        result = await get_strategy(session, creator_id=other_creator_id, strategy_id=strategy_id)
    assert result is None


async def test_update_status_returns_none_for_unknown_strategy():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        result = await update_strategy_status(
            session, creator_id=creator_id, strategy_id="strat_missing", status="active"
        )
    assert result is None


async def test_list_strategies_orders_most_recent_first():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await apply_strategy(session, creator_id=creator_id, summary="first", confidence=0.5, items=[])
        await session.commit()
    async with AsyncSessionLocal() as session:
        await apply_strategy(session, creator_id=creator_id, summary="second", confidence=0.5, items=[])
        await session.commit()

    async with AsyncSessionLocal() as session:
        strategies = await list_strategies(session, creator_id=creator_id)

    assert [s.summary for s in strategies] == ["second", "first"]
