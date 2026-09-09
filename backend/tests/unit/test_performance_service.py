from datetime import datetime, timedelta, timezone

import pytest

from app.core.ids import generate_id
from app.domain.content.models import ContentItem
from app.domain.creator.models import Creator, User
from app.domain.performance.models import PerformanceSnapshot
from app.domain.performance.service import (
    compute_baseline,
    compute_creator_baselines,
    compute_ratios,
    get_latest_snapshot,
    get_performance_overview,
    ingest_performance_snapshot,
    list_performance_snapshots,
    save_diagnosis,
)
from app.infrastructure.db.session import AsyncSessionLocal

_creator_counter = 0


async def _make_creator() -> str:
    global _creator_counter
    _creator_counter += 1
    async with AsyncSessionLocal() as session:
        user = User(email=f"perf{_creator_counter}@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Performance Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def _make_content_item(creator_id: str, item_id: str, *, format: str = "short", status: str = "PUBLISHED") -> None:
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id=item_id, creator_id=creator_id, topic="t", format=format, status=status))
        await session.commit()


async def _add_snapshot(creator_id: str, item_id: str, *, views: int, days_ago: int = 0) -> None:
    async with AsyncSessionLocal() as session:
        session.add(
            PerformanceSnapshot(
                id=generate_id("performance_snapshot"),
                creator_id=creator_id,
                content_item_id=item_id,
                views=views,
                captured_at=datetime.now(timezone.utc) - timedelta(days=days_ago),
            )
        )
        await session.commit()


async def test_ingest_performance_snapshot_creates_a_new_row_each_time():
    """Regression test: ingestion is a time series, not an upsert — two
    calls on the same content item must produce two rows, so a piece's
    trajectory (day 1 vs day 7 views) is preserved."""
    creator_id = await _make_creator()
    await _make_content_item(creator_id, "cnt_perf1")

    async with AsyncSessionLocal() as session:
        item = await session.get(ContentItem, "cnt_perf1")
        await ingest_performance_snapshot(session, creator_id=creator_id, content_item=item, data={"views": 100})
        await session.commit()
    async with AsyncSessionLocal() as session:
        item = await session.get(ContentItem, "cnt_perf1")
        await ingest_performance_snapshot(session, creator_id=creator_id, content_item=item, data={"views": 500})
        await session.commit()

    async with AsyncSessionLocal() as session:
        snapshots = await list_performance_snapshots(session, content_item_id="cnt_perf1")
    assert [s.views for s in snapshots] == [100, 500]


async def test_ingest_performance_snapshot_rejects_non_published_item():
    """Regression test: logging metrics against a draft/in-review item would
    silently contaminate every future baseline for the creator, since
    compute_baseline trusts that any snapshot represents real released
    content."""
    creator_id = await _make_creator()
    await _make_content_item(creator_id, "cnt_perf1b", status="REVIEW")

    async with AsyncSessionLocal() as session:
        item = await session.get(ContentItem, "cnt_perf1b")
        with pytest.raises(ValueError):
            await ingest_performance_snapshot(session, creator_id=creator_id, content_item=item, data={"views": 100})


async def test_get_latest_snapshot_returns_most_recent_by_captured_at():
    creator_id = await _make_creator()
    await _make_content_item(creator_id, "cnt_perf2")
    await _add_snapshot(creator_id, "cnt_perf2", views=100, days_ago=5)
    await _add_snapshot(creator_id, "cnt_perf2", views=900, days_ago=0)

    async with AsyncSessionLocal() as session:
        latest = await get_latest_snapshot(session, content_item_id="cnt_perf2")
    assert latest.views == 900


async def test_compute_baseline_returns_none_below_min_sample():
    creator_id = await _make_creator()
    await _make_content_item(creator_id, "cnt_perf3a")
    await _make_content_item(creator_id, "cnt_perf3b")
    await _add_snapshot(creator_id, "cnt_perf3a", views=100)
    await _add_snapshot(creator_id, "cnt_perf3b", views=200)

    async with AsyncSessionLocal() as session:
        baseline = await compute_baseline(session, creator_id=creator_id, metric="views")
    # Below MIN_BASELINE_SAMPLE (3): still returns the raw sample_size honestly,
    # withholding is the caller's job (compute_creator_baselines).
    assert baseline["sample_size"] == 2


async def test_compute_creator_baselines_withholds_thin_samples():
    """Regression guard for CLAUDE.md §19: with only 2 prior posts, no
    baseline should be reported for that metric at all — not a median
    computed from a sample too small to mean anything."""
    creator_id = await _make_creator()
    await _make_content_item(creator_id, "cnt_perf4")
    await _add_snapshot(creator_id, "cnt_perf4", views=100)
    await _add_snapshot(creator_id, "cnt_perf4", views=200)

    async with AsyncSessionLocal() as session:
        item = await session.get(ContentItem, "cnt_perf4")
        baselines = await compute_creator_baselines(session, creator_id=creator_id, content_item=item)
    assert "views" not in baselines


async def test_compute_creator_baselines_includes_metric_with_enough_samples():
    creator_id = await _make_creator()
    # Four prior posts, distinct from the one being diagnosed below.
    for i, v in enumerate([100, 200, 300, 400]):
        item_id = f"cnt_perf5_prior_{i}"
        await _make_content_item(creator_id, item_id)
        await _add_snapshot(creator_id, item_id, views=v, days_ago=i)
    await _make_content_item(creator_id, "cnt_perf5_target")

    async with AsyncSessionLocal() as session:
        item = await session.get(ContentItem, "cnt_perf5_target")
        baselines = await compute_creator_baselines(session, creator_id=creator_id, content_item=item)
    assert baselines["views"]["overall"]["sample_size"] == 4
    assert baselines["views"]["overall"]["median"] == 250


async def test_compute_baseline_counts_each_content_item_once_not_each_snapshot():
    """Regression test for the core CLAUDE.md §19/§31 concern: a creator who
    has published only ONE real post but logged its metrics three times
    (day 1/3/7 check-ins — the normal, expected ingestion pattern) must not
    have that one post's repeated snapshots satisfy MIN_BASELINE_SAMPLE and
    become a fabricated 3-sample "baseline". Only the post's latest value
    should count, once."""
    creator_id = await _make_creator()
    await _make_content_item(creator_id, "cnt_perf3d")
    await _add_snapshot(creator_id, "cnt_perf3d", views=100, days_ago=7)
    await _add_snapshot(creator_id, "cnt_perf3d", views=800, days_ago=3)
    await _add_snapshot(creator_id, "cnt_perf3d", views=5000, days_ago=0)

    async with AsyncSessionLocal() as session:
        baseline = await compute_baseline(session, creator_id=creator_id, metric="views")
    assert baseline["sample_size"] == 1
    assert baseline["median"] == 5000


async def test_compute_baseline_uses_latest_value_per_item_when_mixed_with_other_posts():
    creator_id = await _make_creator()
    await _make_content_item(creator_id, "cnt_perf3c_repeated")
    await _add_snapshot(creator_id, "cnt_perf3c_repeated", views=100, days_ago=5)
    await _add_snapshot(creator_id, "cnt_perf3c_repeated", views=300, days_ago=0)
    for i, v in enumerate([400, 500]):
        item_id = f"cnt_perf3c_other_{i}"
        await _make_content_item(creator_id, item_id)
        await _add_snapshot(creator_id, item_id, views=v, days_ago=i + 1)

    async with AsyncSessionLocal() as session:
        baseline = await compute_baseline(session, creator_id=creator_id, metric="views")
    # 3 distinct content items, not 4 snapshot rows; the repeated item
    # contributes only its latest value (300), not both 100 and 300.
    assert baseline["sample_size"] == 3
    assert baseline["median"] == 400


async def test_compute_creator_baselines_excludes_the_item_being_diagnosed():
    """Regression test: a content item's own snapshots must not count toward
    its own baseline — otherwise a single very high-performing post could
    inflate its own comparison point and understate how much it
    outperformed everything else."""
    creator_id = await _make_creator()
    for i in range(3):
        item_id = f"cnt_perf6a_{i}"
        await _make_content_item(creator_id, item_id)
        await _add_snapshot(creator_id, item_id, views=100, days_ago=i)
    await _make_content_item(creator_id, "cnt_perf6b")
    await _add_snapshot(creator_id, "cnt_perf6b", views=10000, days_ago=0)

    async with AsyncSessionLocal() as session:
        item = await session.get(ContentItem, "cnt_perf6b")
        baselines = await compute_creator_baselines(session, creator_id=creator_id, content_item=item)
    # cnt_perf6b's own 10000-view snapshot must not appear in its own baseline.
    assert baselines["views"]["overall"]["median"] == 100


async def test_compute_ratios_computed_from_baseline_medians():
    creator_id = await _make_creator()
    await _make_content_item(creator_id, "cnt_perf7")
    async with AsyncSessionLocal() as session:
        snapshot = PerformanceSnapshot(id="perf_ratio_test", creator_id=creator_id, content_item_id="cnt_perf7", views=400)
    baselines = {"views": {"overall": {"median": 200, "sample_size": 5}}}

    ratios = compute_ratios(snapshot, baselines)
    assert ratios["views_vs_overall_median"] == 2.0


async def test_compute_ratios_skips_zero_median_without_crashing():
    """Regression guard: a legitimately-zero baseline median (e.g. a
    creator whose posts typically get 0 saves) must not raise a
    ZeroDivisionError, and must be distinguishable from 'no baseline at
    all' in behavior even though both currently produce no ratio key —
    the raw median is still passed to the agent separately (see
    PerformanceIntelligenceAgent, which receives `baselines` alongside
    `ratios`)."""
    creator_id = await _make_creator()
    await _make_content_item(creator_id, "cnt_perf7b")
    snapshot = PerformanceSnapshot(id="perf_ratio_zero", creator_id=creator_id, content_item_id="cnt_perf7b", saves=50)
    baselines = {"saves": {"overall": {"median": 0, "sample_size": 5}}}

    ratios = compute_ratios(snapshot, baselines)
    assert ratios == {}


async def test_save_diagnosis_persists_ratios_and_diagnosis_into_baseline_comparison():
    creator_id = await _make_creator()
    await _make_content_item(creator_id, "cnt_perf8")
    async with AsyncSessionLocal() as session:
        item = await session.get(ContentItem, "cnt_perf8")
        snapshot = await ingest_performance_snapshot(
            session, creator_id=creator_id, content_item=item, data={"views": 500}
        )
        await session.commit()
        snapshot_id = snapshot.id

    async with AsyncSessionLocal() as session:
        snapshot = await session.get(PerformanceSnapshot, snapshot_id)
        await save_diagnosis(
            session,
            snapshot=snapshot,
            diagnosis={"summary": "did well", "confidence": "medium"},
            ratios={"views_vs_overall_median": 2.0},
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        snapshot = await session.get(PerformanceSnapshot, snapshot_id)
    assert snapshot.baseline_comparison["views_vs_overall_median"] == 2.0
    assert snapshot.baseline_comparison["diagnosis"]["summary"] == "did well"


async def test_get_performance_overview_only_includes_published_items():
    creator_id = await _make_creator()
    await _make_content_item(creator_id, "cnt_perf9_pub", status="PUBLISHED")
    await _make_content_item(creator_id, "cnt_perf9_draft", status="REVIEW")
    await _add_snapshot(creator_id, "cnt_perf9_pub", views=500)

    async with AsyncSessionLocal() as session:
        overview = await get_performance_overview(session, creator_id=creator_id)
    item_ids = [item.id for item, _ in overview]
    assert item_ids == ["cnt_perf9_pub"]
    assert overview[0][1].views == 500
