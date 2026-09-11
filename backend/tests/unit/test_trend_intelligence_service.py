from datetime import datetime, timedelta, timezone

from app.domain.creator.models import Creator, User
from app.domain.research.models import ResearchSignal
from app.domain.research.service import compute_topic_momentum, list_trend_insights, upsert_trend_insights
from app.infrastructure.db.session import AsyncSessionLocal

_creator_counter = 0


async def _make_creator() -> str:
    global _creator_counter
    _creator_counter += 1
    async with AsyncSessionLocal() as session:
        user = User(email=f"trend{_creator_counter}@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Trend Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def _add_signal(creator_id: str, *, topic: str, days_ago: int, signal_id: str) -> None:
    async with AsyncSessionLocal() as session:
        signal = ResearchSignal(
            id=signal_id,
            creator_id=creator_id,
            topic=topic,
            content_features={"summary": f"observation about {topic}"},
        )
        session.add(signal)
        await session.flush()
        # created_at has a Python-side default (TimestampMixin), so backdate
        # it explicitly with a raw UPDATE-equivalent assignment post-flush.
        signal.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        await session.commit()


async def test_compute_topic_momentum_detects_new_topic():
    creator_id = await _make_creator()
    await _add_signal(creator_id, topic="AI productivity", days_ago=1, signal_id="rs_new1")
    await _add_signal(creator_id, topic="AI productivity", days_ago=2, signal_id="rs_new2")

    async with AsyncSessionLocal() as session:
        stats = await compute_topic_momentum(session, creator_id=creator_id)

    key = "ai productivity"
    assert stats[key]["momentum"] == "new"
    assert stats[key]["signal_count"] == 2
    assert stats[key]["recent_signal_count"] == 2


async def test_compute_topic_momentum_detects_rising():
    creator_id = await _make_creator()
    # 1 signal in the prior window, 3 in the recent window -> rising.
    await _add_signal(creator_id, topic="budgeting", days_ago=20, signal_id="rs_r1")
    await _add_signal(creator_id, topic="budgeting", days_ago=5, signal_id="rs_r2")
    await _add_signal(creator_id, topic="budgeting", days_ago=4, signal_id="rs_r3")
    await _add_signal(creator_id, topic="budgeting", days_ago=3, signal_id="rs_r4")

    async with AsyncSessionLocal() as session:
        stats = await compute_topic_momentum(session, creator_id=creator_id)

    assert stats["budgeting"]["momentum"] == "rising"


async def test_compute_topic_momentum_detects_declining():
    creator_id = await _make_creator()
    await _add_signal(creator_id, topic="short-form editing", days_ago=20, signal_id="rs_d1")
    await _add_signal(creator_id, topic="short-form editing", days_ago=18, signal_id="rs_d2")
    await _add_signal(creator_id, topic="short-form editing", days_ago=16, signal_id="rs_d3")
    await _add_signal(creator_id, topic="short-form editing", days_ago=5, signal_id="rs_d4")

    async with AsyncSessionLocal() as session:
        stats = await compute_topic_momentum(session, creator_id=creator_id)

    assert stats["short-form editing"]["momentum"] == "declining"


async def test_compute_topic_momentum_groups_case_insensitively():
    creator_id = await _make_creator()
    await _add_signal(creator_id, topic="Budgeting", days_ago=1, signal_id="rs_c1")
    await _add_signal(creator_id, topic="budgeting", days_ago=2, signal_id="rs_c2")

    async with AsyncSessionLocal() as session:
        stats = await compute_topic_momentum(session, creator_id=creator_id)

    assert len(stats) == 1
    assert stats["budgeting"]["signal_count"] == 2


async def test_upsert_trend_insights_creates_and_updates_in_place():
    creator_id = await _make_creator()
    await _add_signal(creator_id, topic="AI productivity", days_ago=1, signal_id="rs_u1")

    async with AsyncSessionLocal() as session:
        stats = await compute_topic_momentum(session, creator_id=creator_id)
        await upsert_trend_insights(
            session,
            creator_id=creator_id,
            stats=stats,
            agent_insights=[
                {
                    "topic_key": "ai productivity",
                    "saturation_estimate": "medium",
                    "durability": "durable",
                    "relevance_to_creator": "high",
                    "reasoning": "Fits the creator's pillar.",
                    "confidence": "medium",
                }
            ],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        insights = await list_trend_insights(session, creator_id=creator_id)
    assert len(insights) == 1
    assert insights[0].saturation_estimate == "medium"
    first_id = insights[0].id

    # Re-running analysis updates the same row rather than duplicating it.
    async with AsyncSessionLocal() as session:
        stats = await compute_topic_momentum(session, creator_id=creator_id)
        await upsert_trend_insights(
            session,
            creator_id=creator_id,
            stats=stats,
            agent_insights=[
                {
                    "topic_key": "ai productivity",
                    "saturation_estimate": "high",
                    "durability": "durable",
                    "relevance_to_creator": "high",
                    "reasoning": "Now looks saturated.",
                    "confidence": "high",
                }
            ],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        insights = await list_trend_insights(session, creator_id=creator_id)
    assert len(insights) == 1
    assert insights[0].id == first_id
    assert insights[0].saturation_estimate == "high"


async def test_upsert_trend_insights_drops_unknown_topic():
    creator_id = await _make_creator()
    await _add_signal(creator_id, topic="budgeting", days_ago=1, signal_id="rs_k1")

    async with AsyncSessionLocal() as session:
        stats = await compute_topic_momentum(session, creator_id=creator_id)
        await upsert_trend_insights(
            session,
            creator_id=creator_id,
            stats=stats,
            agent_insights=[
                {"topic_key": "a topic never given", "saturation_estimate": "low", "durability": "durable", "relevance_to_creator": "high", "reasoning": "x", "confidence": "low"}
            ],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        insights = await list_trend_insights(session, creator_id=creator_id)
    assert insights == []
