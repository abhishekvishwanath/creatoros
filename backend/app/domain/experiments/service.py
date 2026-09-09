"""Learning Engine (CLAUDE.md §31, §54 item 15).

Converts performance diagnoses into persistent, evidence-linked
`StrategicLearning` rows — the mechanism CLAUDE.md §60 calls "next week's
strategy already knows what happened last week."

This is deliberately NOT an LLM agent. A diagnosis's `associated_factors`
are already the model's qualitative read of *one* post; turning that into a
durable, creator-wide belief is a statistical aggregation job (cluster
recurring factors, count corroborating evidence, threshold on sample size),
not a reasoning job — CLAUDE.md §53 says to prefer a module over a new
agent identity when there's no reasoning gap to fill, and letting a model
"decide" whether a factor has enough evidence would just reintroduce the
opaque-number problem CLAUDE.md §20 already ruled out for ratios.

Every learning must be traceable to >= MIN_LEARNING_EVIDENCE distinct
published posts (CLAUDE.md §19/§31: a single post is never grounds for a
creator-wide rule) and its confidence is derived purely from evidence count
and the diagnosis-reported per-factor confidence — never invented.
"""

import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import generate_id
from app.domain.content.models import ContentItem
from app.domain.experiments.models import StrategicLearning
from app.domain.performance.models import PerformanceSnapshot

MIN_LEARNING_EVIDENCE = 2
# How far a piece's average baseline ratio must sit from 1.0 (its creator's
# own median) before a factor cited alongside it counts as a positive or
# negative signal at all — a piece performing within +/-15% of baseline is
# unremarkable, and clustering factors from "normal" posts would just be
# noise (CLAUDE.md §29: don't overclaim from a weak signal).
RATIO_SIGNIFICANCE_THRESHOLD = 0.15

_FACTOR_CONFIDENCE_WEIGHT = {"low": 0.3, "medium": 0.55, "high": 0.8}
_EVIDENCE_COUNT_WEIGHT = {2: 0.4, 3: 0.55, 4: 0.65}
_EVIDENCE_COUNT_WEIGHT_CAP = 0.75


def _normalize_factor(text: str) -> str:
    return " ".join(text.strip().lower().rstrip(".").split())


def _direction_from_ratios(baseline_comparison: dict) -> Optional[str]:
    """Average every *_vs_overall_median ratio on a snapshot into a single
    directional read. Code-computed, not model-computed (CLAUDE.md §20)."""
    ratios = [v for k, v in baseline_comparison.items() if k.endswith("_vs_overall_median") and isinstance(v, (int, float))]
    if not ratios:
        return None
    avg = statistics.mean(ratios)
    if avg >= 1 + RATIO_SIGNIFICANCE_THRESHOLD:
        return "positive"
    if avg <= 1 - RATIO_SIGNIFICANCE_THRESHOLD:
        return "negative"
    return None


def _evidence_confidence(count: int, factor_confidences: list[str]) -> float:
    count_score = _EVIDENCE_COUNT_WEIGHT.get(count, _EVIDENCE_COUNT_WEIGHT_CAP)
    factor_scores = [_FACTOR_CONFIDENCE_WEIGHT.get(c, 0.3) for c in factor_confidences]
    factor_score = statistics.mean(factor_scores) if factor_scores else 0.3
    return round((count_score + factor_score) / 2, 2)


async def collect_learning_candidates(db: AsyncSession, *, creator_id: str) -> list[dict]:
    """Scans every diagnosed snapshot for this creator, clusters
    `associated_factors` by (normalized factor text, direction), and returns
    only the clusters with enough distinct-content-item corroboration to be
    worth persisting."""
    result = await db.execute(
        select(PerformanceSnapshot, ContentItem.format)
        .join(ContentItem, ContentItem.id == PerformanceSnapshot.content_item_id)
        .where(PerformanceSnapshot.creator_id == creator_id, PerformanceSnapshot.baseline_comparison.isnot(None))
    )

    clusters: dict[tuple[str, str], dict] = {}
    for snapshot, content_format in result.all():
        comparison = snapshot.baseline_comparison or {}
        diagnosis = comparison.get("diagnosis") or {}
        factors = diagnosis.get("associated_factors") or []
        direction = _direction_from_ratios(comparison)
        if direction is None or not factors:
            continue

        for factor in factors:
            label = factor.get("factor")
            if not label:
                continue
            key = (_normalize_factor(label), direction)
            cluster = clusters.setdefault(
                key,
                {
                    "direction": direction,
                    "label": label,
                    "content_item_ids": set(),
                    "formats": set(),
                    "factor_confidences": [],
                    "first_observed_at": snapshot.captured_at,
                },
            )
            cluster["content_item_ids"].add(snapshot.content_item_id)
            cluster["formats"].add(content_format)
            cluster["factor_confidences"].append(factor.get("confidence", "low"))
            cluster["label"] = label  # keep the most recently seen phrasing
            if snapshot.captured_at < cluster["first_observed_at"]:
                cluster["first_observed_at"] = snapshot.captured_at

    return [c for c in clusters.values() if len(c["content_item_ids"]) >= MIN_LEARNING_EVIDENCE]


def _category_key(direction: str, factor_norm: str) -> str:
    """Doubles as the dedup identity for upserts: `category` isn't just a
    display label here, it's a stable slug (direction + normalized factor)
    so re-running sync updates the same row instead of duplicating it."""
    return f"performance/{direction}/{factor_norm.replace(' ', '_')}"


def _statement(direction: str, label: str, count: int) -> str:
    verb = "above-baseline" if direction == "positive" else "below-baseline"
    return f"{label.strip().capitalize()} appears associated with {verb} performance (seen across {count} posts)."


async def sync_learnings(db: AsyncSession, *, creator_id: str) -> list[StrategicLearning]:
    """Idempotent: recomputes candidates from current diagnosis history and
    upserts one StrategicLearning per qualifying cluster. Never deletes —
    evidence for a factor doesn't disappear once observed, it can only grow,
    so `status` stays creator/human-editable rather than this silently
    retracting things. Symmetrically, it also never *resurrects* a learning
    the creator already retracted (or a future flow superseded): once a row
    exists for a category with a non-"active" status, re-syncing skips it
    rather than overwriting the creator's override (CLAUDE.md §3.2)."""
    candidates = await collect_learning_candidates(db, creator_id=creator_id)
    if not candidates:
        return []

    existing_result = await db.execute(
        select(StrategicLearning).where(StrategicLearning.creator_id == creator_id)
    )
    existing_by_category = {row.category: row for row in existing_result.scalars().all()}

    now = datetime.now(timezone.utc)
    touched: list[StrategicLearning] = []
    for cluster in candidates:
        factor_norm = _normalize_factor(cluster["label"])
        category = _category_key(cluster["direction"], factor_norm)
        count = len(cluster["content_item_ids"])
        confidence = _evidence_confidence(count, cluster["factor_confidences"])
        scope = "format-specific" if len(cluster["formats"]) == 1 else "creator-wide"
        statement = _statement(cluster["direction"], cluster["label"], count)

        learning = existing_by_category.get(category)
        if learning is not None and learning.status != "active":
            # The creator already retracted (or a future flow superseded)
            # this exact learning — a fresh sync must never silently
            # resurrect an override they made (CLAUDE.md §3.2: the creator
            # remains in control). Leave it untouched and out of `touched`.
            continue
        if learning is None:
            learning = StrategicLearning(
                id=generate_id("strategic_learning"),
                creator_id=creator_id,
                category=category,
                first_observed_at=cluster["first_observed_at"],
                status="active",
            )
            db.add(learning)
        learning.statement = statement
        learning.evidence_ids = sorted(cluster["content_item_ids"])
        learning.confidence = confidence
        learning.scope = scope
        learning.last_validated_at = now
        touched.append(learning)

    await db.flush()
    return touched


async def list_learnings(
    db: AsyncSession, *, creator_id: str, status_filter: Optional[str] = "active", limit: int = 50
) -> list[StrategicLearning]:
    query = select(StrategicLearning).where(StrategicLearning.creator_id == creator_id)
    if status_filter:
        query = query.where(StrategicLearning.status == status_filter)
    query = query.order_by(StrategicLearning.confidence.desc()).limit(limit)
    result = await db.execute(query)
    return list(result.scalars().all())


async def set_learning_status(
    db: AsyncSession, *, creator_id: str, learning_id: str, status: str
) -> Optional[StrategicLearning]:
    """Lets a creator retract a learning they disagree with (CLAUDE.md §3.2:
    the creator can always override an inference)."""
    result = await db.execute(
        select(StrategicLearning).where(
            StrategicLearning.id == learning_id, StrategicLearning.creator_id == creator_id
        )
    )
    learning = result.scalar_one_or_none()
    if learning is None:
        return None
    learning.status = status
    await db.flush()
    return learning
