"""Performance ingestion + baselines (CLAUDE.md §27-29, §54 items 13-14).

Manual entry only (no live platform-API sync wired up yet, same as content
ingestion and research signals). Ingestion always inserts a new snapshot
row rather than overwriting one, so a piece's trajectory over time (day 1
views vs day 7 views) is preserved as a real time series, not collapsed
into a single point.

Baselines use the median of the creator's own recent history (CLAUDE.md
§28: robust stats over averages, since creator performance is noisy) and
are withheld entirely below MIN_BASELINE_SAMPLE (CLAUDE.md §19: never treat
a small sample as definitive) rather than reported on a thin, misleading
sample.
"""

import statistics
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import generate_id
from app.domain.content.models import ContentItem
from app.domain.performance.models import PerformanceSnapshot

BASELINE_METRICS = (
    "views",
    "watch_time",
    "avg_view_duration",
    "retention",
    "likes",
    "comments",
    "shares",
    "saves",
    "followers_gained",
    "profile_visits",
)
MIN_BASELINE_SAMPLE = 3
DEFAULT_BASELINE_WINDOW = 20


async def ingest_performance_snapshot(
    db: AsyncSession, *, creator_id: str, content_item: ContentItem, data: dict
) -> PerformanceSnapshot:
    """Restricted to PUBLISHED items: metrics logged against a draft/
    in-review item would silently contaminate every future baseline
    (compute_baseline has no status filter of its own — it trusts that only
    real, released content ever gets a snapshot in the first place)."""
    if content_item.status != "PUBLISHED":
        raise ValueError(
            f"Cannot log performance for a content item that isn't PUBLISHED yet (status={content_item.status!r})."
        )
    snapshot = PerformanceSnapshot(
        id=generate_id("performance_snapshot"),
        creator_id=creator_id,
        content_item_id=content_item.id,
        views=data.get("views"),
        watch_time=data.get("watch_time"),
        avg_view_duration=data.get("avg_view_duration"),
        retention=data.get("retention"),
        likes=data.get("likes"),
        comments=data.get("comments"),
        shares=data.get("shares"),
        saves=data.get("saves"),
        followers_gained=data.get("followers_gained"),
        profile_visits=data.get("profile_visits"),
        captured_at=data.get("captured_at") or datetime.now(timezone.utc),
    )
    db.add(snapshot)
    await db.flush()
    return snapshot


async def list_performance_snapshots(db: AsyncSession, *, content_item_id: str) -> list[PerformanceSnapshot]:
    result = await db.execute(
        select(PerformanceSnapshot)
        .where(PerformanceSnapshot.content_item_id == content_item_id)
        .order_by(PerformanceSnapshot.captured_at)
    )
    return list(result.scalars().all())


async def get_latest_snapshot(db: AsyncSession, *, content_item_id: str) -> Optional[PerformanceSnapshot]:
    result = await db.execute(
        select(PerformanceSnapshot)
        .where(PerformanceSnapshot.content_item_id == content_item_id)
        .order_by(desc(PerformanceSnapshot.captured_at))
        .limit(1)
    )
    return result.scalar_one_or_none()


async def compute_baseline(
    db: AsyncSession,
    *,
    creator_id: str,
    metric: str,
    limit: int = DEFAULT_BASELINE_WINDOW,
    format: Optional[str] = None,
    exclude_content_item_id: Optional[str] = None,
) -> dict:
    """Median of the last `limit` *distinct content items'* most recent
    non-null value for one metric, optionally scoped to a content format
    (CLAUDE.md §28's "median retention for same format" example).
    `exclude_content_item_id` keeps the piece being diagnosed out of its own
    baseline.

    One row per content item, not per snapshot: ingestion intentionally
    writes a new PerformanceSnapshot on every check-in (day 1, day 3, day 7
    — see ingest_performance_snapshot), so a single post logged three times
    must count once in the baseline, not three times. Without this, a
    creator with only one published post who logs it repeatedly could see
    that one post satisfy MIN_BASELINE_SAMPLE and become its own "baseline"
    — exactly the single-post-becomes-a-rule failure CLAUDE.md §19/§31 warn
    against."""
    column = getattr(PerformanceSnapshot, metric)
    latest_per_item = (
        select(
            PerformanceSnapshot.content_item_id,
            column.label("metric_value"),
            PerformanceSnapshot.captured_at,
        )
        .where(PerformanceSnapshot.creator_id == creator_id, column.isnot(None))
    )
    if format is not None:
        latest_per_item = latest_per_item.join(
            ContentItem, ContentItem.id == PerformanceSnapshot.content_item_id
        ).where(ContentItem.format == format)
    if exclude_content_item_id is not None:
        latest_per_item = latest_per_item.where(PerformanceSnapshot.content_item_id != exclude_content_item_id)
    latest_per_item = latest_per_item.distinct(PerformanceSnapshot.content_item_id).order_by(
        PerformanceSnapshot.content_item_id, desc(PerformanceSnapshot.captured_at)
    )
    subquery = latest_per_item.subquery()

    query = select(subquery.c.metric_value).order_by(desc(subquery.c.captured_at)).limit(limit)
    result = await db.execute(query)
    values = [v for (v,) in result.all()]
    if not values:
        return {"median": None, "sample_size": 0}
    return {"median": statistics.median(values), "sample_size": len(values)}


async def compute_creator_baselines(db: AsyncSession, *, creator_id: str, content_item: ContentItem) -> dict:
    """Per-metric creator-wide and same-format baselines, only included when
    there's enough history to mean anything (MIN_BASELINE_SAMPLE)."""
    baselines: dict = {}
    for metric in BASELINE_METRICS:
        entry: dict = {}
        overall = await compute_baseline(
            db, creator_id=creator_id, metric=metric, exclude_content_item_id=content_item.id
        )
        if overall["sample_size"] >= MIN_BASELINE_SAMPLE:
            entry["overall"] = overall
        if content_item.format:
            by_format = await compute_baseline(
                db,
                creator_id=creator_id,
                metric=metric,
                format=content_item.format,
                exclude_content_item_id=content_item.id,
            )
            if by_format["sample_size"] >= MIN_BASELINE_SAMPLE:
                entry["by_format"] = by_format
        if entry:
            baselines[metric] = entry
    return baselines


def compute_ratios(snapshot: PerformanceSnapshot, baselines: dict) -> dict:
    """This piece's metrics vs. its creator/format baselines, computed here
    in code — never left for the model to eyeball or invent (CLAUDE.md §20:
    no opaque model-authored numbers). The Performance Intelligence Agent
    receives these ratios as given fact and only reasons qualitatively about
    what might explain them."""
    ratios: dict = {}
    for metric, entry in baselines.items():
        value = getattr(snapshot, metric, None)
        if value is None:
            continue
        for scope in ("overall", "by_format"):
            median = entry.get(scope, {}).get("median")
            # None means "no baseline for this scope" (skip); 0 is a real,
            # legitimate median (e.g. a creator whose posts typically get 0
            # saves) that we still can't safely divide by — a ratio against
            # a zero baseline is mathematically undefined, not "no data".
            # The raw median (0) is still visible to the agent via the
            # `baselines` context passed alongside `ratios`, so that signal
            # isn't lost even though no ratio number can represent it.
            if median is not None and median != 0:
                ratios[f"{metric}_vs_{scope}_median"] = round(value / median, 2)
    return ratios


async def save_diagnosis(
    db: AsyncSession, *, snapshot: PerformanceSnapshot, diagnosis: dict, ratios: dict
) -> PerformanceSnapshot:
    """Persists into PerformanceSnapshot.baseline_comparison — the field's
    own docstring already frames it as exactly this
    ({"median_views_30d": ..., "views_vs_baseline_ratio": ...}) — so the
    diagnosis survives past this one request instead of being recomputed
    (and re-charged) on every page load, and is available as an input to a
    future Learning Engine phase (CLAUDE.md §31)."""
    snapshot.baseline_comparison = {**ratios, "diagnosis": diagnosis}
    await db.flush()
    return snapshot


async def get_performance_overview(
    db: AsyncSession, *, creator_id: str
) -> list[tuple[ContentItem, Optional[PerformanceSnapshot]]]:
    """One row per published content item with its most recent snapshot, if
    any — the Analytics page's "what happened across everything" view
    (CLAUDE.md §38 Analytics IA)."""
    result = await db.execute(
        select(ContentItem)
        .where(ContentItem.creator_id == creator_id, ContentItem.status == "PUBLISHED")
        .order_by(desc(ContentItem.updated_at))
    )
    items = list(result.scalars().all())
    overview = []
    for item in items:
        latest = await get_latest_snapshot(db, content_item_id=item.id)
        overview.append((item, latest))
    return overview
