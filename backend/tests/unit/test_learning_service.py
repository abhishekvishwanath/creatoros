from datetime import datetime, timedelta, timezone

from app.core.ids import generate_id
from app.domain.content.models import ContentItem
from app.domain.creator.models import Creator, User
from app.domain.experiments.models import StrategicLearning
from app.domain.experiments.service import (
    MIN_LEARNING_EVIDENCE,
    collect_learning_candidates,
    list_learnings,
    set_learning_status,
    sync_learnings,
)
from app.domain.performance.models import PerformanceSnapshot
from app.infrastructure.db.session import AsyncSessionLocal

_creator_counter = 0


async def _make_creator() -> str:
    global _creator_counter
    _creator_counter += 1
    async with AsyncSessionLocal() as session:
        user = User(email=f"learn{_creator_counter}@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Learning Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def _make_diagnosed_item(
    creator_id: str,
    item_id: str,
    *,
    format: str = "short",
    ratio: float = 1.6,
    factors: list[dict],
    days_ago: int = 0,
) -> None:
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id=item_id, creator_id=creator_id, topic="t", format=format, status="PUBLISHED"))
        session.add(
            PerformanceSnapshot(
                id=generate_id("performance_snapshot"),
                creator_id=creator_id,
                content_item_id=item_id,
                views=1000,
                captured_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
                baseline_comparison={
                    "views_vs_overall_median": ratio,
                    "diagnosis": {
                        "summary": "diagnosis",
                        "associated_factors": factors,
                        "confidence": "medium",
                    },
                },
            )
        )
        await session.commit()


POSITIVE_FACTOR = [{"factor": "Contrarian hook", "confidence": "medium", "note": "n"}]
NEGATIVE_FACTOR = [{"factor": "Long intro", "confidence": "low", "note": "n"}]


async def test_collect_candidates_requires_minimum_distinct_evidence():
    """Regression guard for CLAUDE.md §19/§31: a factor cited by only one
    post must never surface as a candidate, since a single post is never
    grounds for a creator-wide rule."""
    creator_id = await _make_creator()
    await _make_diagnosed_item(creator_id, "cnt_l1", factors=POSITIVE_FACTOR)

    async with AsyncSessionLocal() as session:
        candidates = await collect_learning_candidates(session, creator_id=creator_id)
    assert candidates == []
    assert MIN_LEARNING_EVIDENCE == 2


async def test_collect_candidates_clusters_matching_factor_across_posts():
    creator_id = await _make_creator()
    await _make_diagnosed_item(creator_id, "cnt_l1", factors=POSITIVE_FACTOR, ratio=1.6)
    await _make_diagnosed_item(creator_id, "cnt_l2", factors=[{"factor": "contrarian hook.", "confidence": "high", "note": "n"}], ratio=1.8)

    async with AsyncSessionLocal() as session:
        candidates = await collect_learning_candidates(session, creator_id=creator_id)

    assert len(candidates) == 1
    assert candidates[0]["direction"] == "positive"
    assert len(candidates[0]["evidence_ids"]) == 2


async def test_collect_candidates_ignores_posts_within_baseline_noise_band():
    """A ratio close to 1.0 (within RATIO_SIGNIFICANCE_THRESHOLD) isn't a
    real signal (CLAUDE.md §29: don't overclaim from a weak signal)."""
    creator_id = await _make_creator()
    await _make_diagnosed_item(creator_id, "cnt_l1", factors=POSITIVE_FACTOR, ratio=1.05)
    await _make_diagnosed_item(creator_id, "cnt_l2", factors=POSITIVE_FACTOR, ratio=0.95)

    async with AsyncSessionLocal() as session:
        candidates = await collect_learning_candidates(session, creator_id=creator_id)
    assert candidates == []


async def test_collect_candidates_keeps_positive_and_negative_directions_separate():
    creator_id = await _make_creator()
    await _make_diagnosed_item(creator_id, "cnt_l1", factors=POSITIVE_FACTOR, ratio=1.6)
    await _make_diagnosed_item(creator_id, "cnt_l2", factors=POSITIVE_FACTOR, ratio=1.7)
    await _make_diagnosed_item(creator_id, "cnt_l3", factors=[{"factor": "Contrarian hook", "confidence": "low", "note": "n"}], ratio=0.5)
    await _make_diagnosed_item(creator_id, "cnt_l4", factors=[{"factor": "Contrarian hook", "confidence": "low", "note": "n"}], ratio=0.4)

    async with AsyncSessionLocal() as session:
        candidates = await collect_learning_candidates(session, creator_id=creator_id)

    directions = {c["direction"] for c in candidates}
    assert directions == {"positive", "negative"}


async def test_sync_learnings_persists_and_is_idempotent():
    creator_id = await _make_creator()
    await _make_diagnosed_item(creator_id, "cnt_l1", factors=POSITIVE_FACTOR, ratio=1.6)
    await _make_diagnosed_item(creator_id, "cnt_l2", factors=POSITIVE_FACTOR, ratio=1.8)

    async with AsyncSessionLocal() as session:
        learnings = await sync_learnings(session, creator_id=creator_id)
        await session.commit()
    assert len(learnings) == 1
    first_id = learnings[0].id
    assert "contrarian hook" in learnings[0].statement.lower()
    assert learnings[0].evidence_ids == sorted(["cnt_l1", "cnt_l2"])

    # A second post citing the same factor should update the SAME row
    # (matched via category), not create a duplicate.
    await _make_diagnosed_item(creator_id, "cnt_l3", factors=POSITIVE_FACTOR, ratio=1.9)
    async with AsyncSessionLocal() as session:
        learnings = await sync_learnings(session, creator_id=creator_id)
        await session.commit()
    assert len(learnings) == 1
    assert learnings[0].id == first_id
    assert len(learnings[0].evidence_ids) == 3

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            StrategicLearning.__table__.select().where(StrategicLearning.creator_id == creator_id)
        )
        rows = result.all()
    assert len(rows) == 1


async def test_confidence_increases_with_more_evidence():
    creator_a = await _make_creator()
    await _make_diagnosed_item(creator_a, "cnt_a1", factors=[{"factor": "x", "confidence": "low", "note": "n"}], ratio=1.6)
    await _make_diagnosed_item(creator_a, "cnt_a2", factors=[{"factor": "x", "confidence": "low", "note": "n"}], ratio=1.6)

    creator_b = await _make_creator()
    for i in range(5):
        await _make_diagnosed_item(
            creator_b, f"cnt_b{i}", factors=[{"factor": "x", "confidence": "high", "note": "n"}], ratio=1.6
        )

    async with AsyncSessionLocal() as session:
        low_evidence = await sync_learnings(session, creator_id=creator_a)
        high_evidence = await sync_learnings(session, creator_id=creator_b)
        await session.commit()

    assert high_evidence[0].confidence > low_evidence[0].confidence


async def test_scope_is_format_specific_when_all_evidence_shares_a_format_else_creator_wide():
    creator_id = await _make_creator()
    await _make_diagnosed_item(creator_id, "cnt_l1", format="short", factors=POSITIVE_FACTOR, ratio=1.6)
    await _make_diagnosed_item(creator_id, "cnt_l2", format="short", factors=POSITIVE_FACTOR, ratio=1.8)
    await _make_diagnosed_item(creator_id, "cnt_l3", format="carousel", factors=POSITIVE_FACTOR, ratio=1.7)

    async with AsyncSessionLocal() as session:
        [learning] = await sync_learnings(session, creator_id=creator_id)
        await session.commit()
    assert learning.scope == "creator-wide"


async def test_list_learnings_filters_by_status():
    creator_id = await _make_creator()
    await _make_diagnosed_item(creator_id, "cnt_l1", factors=POSITIVE_FACTOR, ratio=1.6)
    await _make_diagnosed_item(creator_id, "cnt_l2", factors=POSITIVE_FACTOR, ratio=1.8)

    async with AsyncSessionLocal() as session:
        [learning] = await sync_learnings(session, creator_id=creator_id)
        await session.commit()
        learning_id = learning.id

    async with AsyncSessionLocal() as session:
        active = await list_learnings(session, creator_id=creator_id, status_filter="active")
    assert len(active) == 1

    async with AsyncSessionLocal() as session:
        updated = await set_learning_status(session, creator_id=creator_id, learning_id=learning_id, status="retracted")
        await session.commit()
    assert updated.status == "retracted"

    async with AsyncSessionLocal() as session:
        active_after = await list_learnings(session, creator_id=creator_id, status_filter="active")
        retracted = await list_learnings(session, creator_id=creator_id, status_filter="retracted")
    assert active_after == []
    assert len(retracted) == 1


async def test_sync_does_not_resurrect_a_retracted_learning():
    """Regression guard for CLAUDE.md §3.2: a creator's 'not accurate' override
    must survive a later re-sync, even though the same evidence cluster still
    exists (evidence never disappears once observed)."""
    creator_id = await _make_creator()
    await _make_diagnosed_item(creator_id, "cnt_l1", factors=POSITIVE_FACTOR, ratio=1.6)
    await _make_diagnosed_item(creator_id, "cnt_l2", factors=POSITIVE_FACTOR, ratio=1.8)

    async with AsyncSessionLocal() as session:
        [learning] = await sync_learnings(session, creator_id=creator_id)
        await session.commit()
        learning_id = learning.id

    async with AsyncSessionLocal() as session:
        await set_learning_status(session, creator_id=creator_id, learning_id=learning_id, status="retracted")
        await session.commit()

    # A third post reinforcing the same factor shouldn't flip it back to active.
    await _make_diagnosed_item(creator_id, "cnt_l3", factors=POSITIVE_FACTOR, ratio=1.9)
    async with AsyncSessionLocal() as session:
        touched = await sync_learnings(session, creator_id=creator_id)
        await session.commit()
    assert touched == []

    async with AsyncSessionLocal() as session:
        learning = await session.get(StrategicLearning, learning_id)
    assert learning.status == "retracted"

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            StrategicLearning.__table__.select().where(StrategicLearning.creator_id == creator_id)
        )
        rows = result.all()
    assert len(rows) == 1  # no duplicate row created for the same category


async def test_duplicate_category_for_same_creator_is_rejected_at_db_level():
    """Regression guard: the unique constraint on (creator_id, category) is
    the backstop against a race between two concurrent syncs (same bug class
    as CalendarEvent's content_item_id constraint from Phase 11)."""
    from sqlalchemy.exc import IntegrityError

    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(
            StrategicLearning(
                id=generate_id("strategic_learning"),
                creator_id=creator_id,
                statement="a",
                category="performance/positive/contrarian_hook",
                confidence=0.5,
                first_observed_at=datetime.now(timezone.utc),
            )
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        session.add(
            StrategicLearning(
                id=generate_id("strategic_learning"),
                creator_id=creator_id,
                statement="b",
                category="performance/positive/contrarian_hook",
                confidence=0.5,
                first_observed_at=datetime.now(timezone.utc),
            )
        )
        try:
            await session.commit()
            assert False, "expected IntegrityError"
        except IntegrityError:
            await session.rollback()


async def test_set_learning_status_returns_none_for_other_creators_learning():
    """Tenant isolation (CLAUDE.md §46): a creator must never be able to
    mutate another creator's learning by id."""
    creator_a = await _make_creator()
    creator_b = await _make_creator()
    await _make_diagnosed_item(creator_a, "cnt_l1", factors=POSITIVE_FACTOR, ratio=1.6)
    await _make_diagnosed_item(creator_a, "cnt_l2", factors=POSITIVE_FACTOR, ratio=1.8)

    async with AsyncSessionLocal() as session:
        [learning] = await sync_learnings(session, creator_id=creator_a)
        await session.commit()
        learning_id = learning.id

    async with AsyncSessionLocal() as session:
        result = await set_learning_status(session, creator_id=creator_b, learning_id=learning_id, status="retracted")
    assert result is None
