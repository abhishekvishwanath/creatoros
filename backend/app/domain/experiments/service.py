"""Experimentation + Learning Engine (CLAUDE.md §30-31, §54 item 15).

Two related but distinct jobs live in this module, matching the domain
package's two model groups (app/domain/experiments/models.py):

1. Experiment CRUD + evaluation (CLAUDE.md §30, §11.11 Experimentation
   Agent): a creator- or Strategy-Agent-formulated hypothesis, a planned
   test/control split, and a rule-based statistical comparison (medians,
   sample sizes — computed here in code, never by a model, CLAUDE.md §20)
   that the Experimentation Agent then reasons over qualitatively.

2. The Learning Engine: converts performance diagnoses into persistent,
   evidence-linked `StrategicLearning` rows — the mechanism CLAUDE.md §60
   calls "next week's strategy already knows what happened last week."
   This half is deliberately NOT an LLM agent. A diagnosis's
   `associated_factors` are already the model's qualitative read of *one*
   post; turning that into a durable, creator-wide belief is a statistical
   aggregation job (cluster recurring factors, count corroborating
   evidence, threshold on sample size), not a reasoning job — CLAUDE.md
   §53 says to prefer a module over a new agent identity when there's no
   reasoning gap to fill, and letting a model "decide" whether a factor
   has enough evidence would just reintroduce the opaque-number problem
   CLAUDE.md §20 already ruled out for ratios.

Every learning — whether clustered from performance/commercial evidence or
promoted directly from one completed experiment — must be traceable to
real sample size (CLAUDE.md §19/§31: a single post is never grounds for a
creator-wide rule) and its confidence is derived purely from evidence
count/statistics, never invented.
"""

import statistics
from collections import defaultdict
from datetime import date, datetime, timezone
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import generate_id
from app.domain.commercial.models import Brand, BrandOpportunity, OutreachThread
from app.domain.content.models import ContentItem
from app.domain.experiments.models import Experiment, ExperimentResult, StrategicLearning
from app.domain.memory.service import store_embedding
from app.domain.performance.models import PerformanceSnapshot

# Same rigor as MIN_LEARNING_EVIDENCE below, applied per group: a metric
# needs at least this many results in *both* the test and control groups
# before a delta between their medians means anything (CLAUDE.md §19: a
# tiny sample isn't definitive evidence either way).
MIN_EXPERIMENT_GROUP_EVIDENCE = 2


async def create_experiment(
    db: AsyncSession,
    *,
    creator_id: str,
    hypothesis: str,
    variable: Optional[str] = None,
    control_reference: Optional[str] = None,
    planned_test_set: Optional[list] = None,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> Experiment:
    experiment = Experiment(
        id=generate_id("experiment"),
        creator_id=creator_id,
        hypothesis=hypothesis,
        variable=variable,
        control_reference=control_reference,
        planned_test_set=planned_test_set,
        start_date=start_date,
        end_date=end_date,
    )
    db.add(experiment)
    await db.flush()
    return experiment


async def list_experiments(
    db: AsyncSession, *, creator_id: str, status_filter: Optional[str] = None
) -> list[Experiment]:
    query = select(Experiment).where(Experiment.creator_id == creator_id)
    if status_filter:
        query = query.where(Experiment.status == status_filter)
    query = query.order_by(Experiment.created_at.desc())
    result = await db.execute(query)
    return list(result.scalars().all())


async def get_experiment(db: AsyncSession, *, creator_id: str, experiment_id: str) -> Optional[Experiment]:
    result = await db.execute(
        select(Experiment).where(Experiment.id == experiment_id, Experiment.creator_id == creator_id)
    )
    return result.scalar_one_or_none()


_EXPERIMENT_STATUS_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "running": ("planned",),
    "completed": ("planned", "running"),
    "abandoned": ("planned", "running"),
}


async def set_experiment_status(db: AsyncSession, *, experiment: Experiment, status: str) -> Experiment:
    """Manual, creator-driven transitions (mirrors
    app/domain/content/service.py::mark_content_stage) — a direct user
    action, so an invalid transition raises rather than silently no-op'ing.
    `evaluate_experiment` below also sets status to "completed" itself once
    it has a real conclusion, so this exists mainly for "abandoned" and for
    starting a "planned" experiment running."""
    if status not in _EXPERIMENT_STATUS_TRANSITIONS:
        raise ValueError(f"{status!r} is not a valid experiment status transition target.")
    allowed_from = _EXPERIMENT_STATUS_TRANSITIONS[status]
    if experiment.status not in allowed_from:
        raise ValueError(f"Cannot move to {status!r} from status {experiment.status!r} (expected one of {allowed_from}).")
    experiment.status = status
    await db.flush()
    return experiment


async def add_experiment_result(
    db: AsyncSession,
    *,
    experiment_id: str,
    content_item_id: Optional[str],
    metric_name: str,
    metric_value: float,
    group: str,
) -> ExperimentResult:
    result = ExperimentResult(
        id=generate_id("experiment_result"),
        experiment_id=experiment_id,
        content_item_id=content_item_id,
        metric_name=metric_name,
        metric_value=metric_value,
        group=group,
    )
    db.add(result)
    await db.flush()
    return result


async def list_experiment_results(db: AsyncSession, *, experiment_id: str) -> list[ExperimentResult]:
    result = await db.execute(
        select(ExperimentResult).where(ExperimentResult.experiment_id == experiment_id).order_by(ExperimentResult.created_at)
    )
    return list(result.scalars().all())


def compute_experiment_stats(results: list[ExperimentResult]) -> dict[str, dict]:
    """Rule-based, code-computed comparison of test vs. control groups, one
    entry per metric_name present (CLAUDE.md §20: a model reasons over
    numbers it's given as fact, it never invents or recomputes them). Only
    metrics with at least MIN_EXPERIMENT_GROUP_EVIDENCE results in *both*
    groups get a delta — an unbalanced or thin comparison would just be
    noise wearing a stats-shaped label (CLAUDE.md §29 spirit, applied to
    experiments instead of single-post diagnoses)."""
    by_metric: dict[str, dict[str, list[float]]] = defaultdict(lambda: {"test": [], "control": []})
    for r in results:
        if r.group in ("test", "control"):
            by_metric[r.metric_name][r.group].append(r.metric_value)

    stats: dict[str, dict] = {}
    for metric_name, groups in by_metric.items():
        test_values, control_values = groups["test"], groups["control"]
        entry = {
            "test_n": len(test_values),
            "control_n": len(control_values),
            "test_median": statistics.median(test_values) if test_values else None,
            "control_median": statistics.median(control_values) if control_values else None,
            "adequate_evidence": len(test_values) >= MIN_EXPERIMENT_GROUP_EVIDENCE
            and len(control_values) >= MIN_EXPERIMENT_GROUP_EVIDENCE,
        }
        if entry["test_median"] is not None and entry["control_median"] is not None:
            entry["delta"] = entry["test_median"] - entry["control_median"]
            entry["pct_delta"] = (entry["delta"] / entry["control_median"]) if entry["control_median"] else None
        stats[metric_name] = entry
    return stats


async def apply_experiment_evaluation(
    db: AsyncSession, *, experiment: Experiment, data: dict, stats: dict, results: list[ExperimentResult]
) -> Experiment:
    """Persists the Experimentation Agent's qualitative read (conclusion,
    confidence, next_action, whether to retain the hypothesis) alongside the
    code-computed `stats` this module already produced — the model's output
    is reasoning ABOUT those numbers, never a replacement for them, so both
    are stored (CLAUDE.md §20). Moves the experiment to "completed": an
    evaluation is a real conclusion, not a draft (a creator who disagrees
    can still reopen it via set_experiment_status)."""
    experiment.results = stats
    experiment.confidence = data.get("confidence")
    experiment.conclusion = data.get("conclusion")
    experiment.next_action = data.get("next_action")
    if experiment.status not in ("completed", "abandoned"):
        experiment.status = "completed"
    await db.flush()

    if data.get("retain_hypothesis"):
        evidence_ids = sorted({r.content_item_id for r in results if r.content_item_id})
        await _promote_experiment_to_learning(db, experiment=experiment, evidence_ids=evidence_ids)

    return experiment


async def _promote_experiment_to_learning(
    db: AsyncSession, *, experiment: Experiment, evidence_ids: list[str]
) -> StrategicLearning:
    """A completed, retained experiment IS its own evidence unit (its
    >=MIN_EXPERIMENT_GROUP_EVIDENCE-per-group results already satisfy
    CLAUDE.md §19's "don't generalize from one post" bar) — unlike
    sync_learnings/sync_commercial_learnings below, this doesn't cluster
    across many diagnoses, it promotes one experiment's own conclusion
    directly. category is keyed to the experiment id so re-evaluating the
    same experiment updates its learning in place rather than duplicating
    it (same UniqueConstraint(creator_id, category) as the cluster-based
    learnings). scope is always "temporary experiment" (CLAUDE.md §5.3/§31)
    — a single experiment, however well-run, is exactly the kind of
    knowledge that should stay flagged as provisional rather than be
    silently upgraded to "creator-wide" the way a multi-post cluster can be."""
    category = f"experiment/{experiment.id}"
    result = await db.execute(
        select(StrategicLearning).where(StrategicLearning.creator_id == experiment.creator_id, StrategicLearning.category == category)
    )
    learning = result.scalar_one_or_none()
    confidence_value = {"low": 0.3, "medium": 0.55, "high": 0.75}.get(experiment.confidence or "", 0.3)

    if learning is None:
        learning = StrategicLearning(
            id=generate_id("strategic_learning"),
            creator_id=experiment.creator_id,
            category=category,
            scope="temporary experiment",
        )
        db.add(learning)

    learning.statement = experiment.conclusion or experiment.hypothesis
    learning.confidence = confidence_value
    learning.evidence_ids = evidence_ids
    learning.last_validated_at = datetime.now(timezone.utc)
    learning.status = "active"
    await db.flush()
    await store_embedding(db, creator_id=experiment.creator_id, source_type="learning", text=learning.statement)
    return learning

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
                    # Named to match the commercial-loop collector's
                    # equivalent field — both feed the same shared upsert
                    # engine below (_upsert_learning_clusters).
                    "evidence_ids": set(),
                    "formats": set(),
                    "factor_confidences": [],
                    "first_observed_at": snapshot.captured_at,
                },
            )
            cluster["evidence_ids"].add(snapshot.content_item_id)
            cluster["formats"].add(content_format)
            cluster["factor_confidences"].append(factor.get("confidence", "low"))
            cluster["label"] = label  # keep the most recently seen phrasing
            if snapshot.captured_at < cluster["first_observed_at"]:
                cluster["first_observed_at"] = snapshot.captured_at

    return [c for c in clusters.values() if len(c["evidence_ids"]) >= MIN_LEARNING_EVIDENCE]


def _category_key(direction: str, factor_norm: str) -> str:
    """Doubles as the dedup identity for upserts: `category` isn't just a
    display label here, it's a stable slug (direction + normalized factor)
    so re-running sync updates the same row instead of duplicating it."""
    return f"performance/{direction}/{factor_norm.replace(' ', '_')}"


def _statement(direction: str, label: str, count: int) -> str:
    verb = "above-baseline" if direction == "positive" else "below-baseline"
    return f"{label.strip().capitalize()} appears associated with {verb} performance (seen across {count} posts)."


async def _upsert_learning_clusters(
    db: AsyncSession,
    *,
    creator_id: str,
    candidates: list[dict],
    category_fn,
    statement_fn,
    confidence_fn,
    scope_fn,
) -> list[StrategicLearning]:
    """Shared upsert-by-category engine behind both sync_learnings and
    sync_commercial_learnings (CLAUDE.md §3.7 — the two loops' clustering
    logic differs, but the persistence discipline is identical and belongs
    in exactly one place): idempotent, never deletes, and never
    *resurrects* a learning the creator already retracted (or a future flow
    superseded) — once a row exists for a category with a non-"active"
    status, re-syncing skips it rather than overwriting the creator's
    override (CLAUDE.md §3.2). Each `*_fn` derives one field from a
    cluster dict — the two callers differ only in these, not in the
    upsert/override-preservation logic itself."""
    if not candidates:
        return []

    existing_result = await db.execute(select(StrategicLearning).where(StrategicLearning.creator_id == creator_id))
    existing_by_category = {row.category: row for row in existing_result.scalars().all()}

    now = datetime.now(timezone.utc)
    touched: list[StrategicLearning] = []
    for cluster in candidates:
        category = category_fn(cluster)

        learning = existing_by_category.get(category)
        if learning is not None and learning.status != "active":
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
        learning.statement = statement_fn(cluster)
        learning.evidence_ids = sorted(cluster["evidence_ids"])
        learning.confidence = confidence_fn(cluster)
        learning.scope = scope_fn(cluster)
        learning.last_validated_at = now
        touched.append(learning)

    await db.flush()
    for learning in touched:
        await store_embedding(db, creator_id=creator_id, source_type="learning", text=learning.statement)
    return touched


async def sync_learnings(db: AsyncSession, *, creator_id: str) -> list[StrategicLearning]:
    """Idempotent: recomputes candidates from current diagnosis history and
    upserts one StrategicLearning per qualifying cluster (see
    _upsert_learning_clusters for the shared persistence discipline)."""
    candidates = await collect_learning_candidates(db, creator_id=creator_id)
    return await _upsert_learning_clusters(
        db,
        creator_id=creator_id,
        candidates=candidates,
        category_fn=lambda c: _category_key(c["direction"], _normalize_factor(c["label"])),
        statement_fn=lambda c: _statement(c["direction"], c["label"], len(c["evidence_ids"])),
        confidence_fn=lambda c: _evidence_confidence(len(c["evidence_ids"]), c["factor_confidences"]),
        scope_fn=lambda c: "format-specific" if len(c["formats"]) == 1 else "creator-wide",
    )


# --- Commercial learning (CLAUDE.md Part II §72, Phase 8) -------------------
# Same table, same engine, deliberately reused rather than duplicated
# (CLAUDE.md §3.7) — this is what makes a finding like "AI-tool brands
# outperform generic SaaS for this creator" readable by both
# StrategyEngineAgent/ContentArchitectAgent (content side, already wired to
# read context.strategic_learnings) and BrandIntelligenceAgent's
# historical_category_fit scoring dimension (commercial side, already
# reading the same field) with zero new plumbing on either side.

# Only outcomes with a clear enough directional signal are counted at all —
# an archived thread could mean "brand said no", "creator got busy", or
# "no longer relevant" with no way to tell which, so (like a performance
# ratio within +/-15% of baseline) it contributes nothing either way
# (CLAUDE.md §29: don't overclaim from an ambiguous signal).
_OUTCOME_DIRECTION = {"deal_confirmed": "positive", "declined_by_creator": "negative"}


def outcome_has_learning_signal(outcome: Optional[str]) -> bool:
    """Lets a caller (e.g. the decision route) skip triggering a sync
    entirely for an outcome that can never contribute a cluster — same
    source of truth as _OUTCOME_DIRECTION, exposed instead of duplicated."""
    return outcome in _OUTCOME_DIRECTION


async def collect_commercial_learning_candidates(db: AsyncSession, *, creator_id: str) -> list[dict]:
    """Mirrors collect_learning_candidates for the commercial loop: clusters
    resolved OutreachThread outcomes by brand category, and returns only
    clusters with enough distinct-thread corroboration (MIN_LEARNING_EVIDENCE)
    to be worth persisting."""
    result = await db.execute(
        select(OutreachThread, Brand.category)
        .join(BrandOpportunity, BrandOpportunity.id == OutreachThread.brand_opportunity_id)
        .join(Brand, Brand.id == BrandOpportunity.brand_id)
        .where(OutreachThread.creator_id == creator_id, OutreachThread.outcome.isnot(None))
    )

    clusters: dict[tuple[str, str], dict] = {}
    for thread, category in result.all():
        if not category:
            continue
        direction = _OUTCOME_DIRECTION.get(thread.outcome)
        if direction is None:
            continue
        key = (_normalize_factor(category), direction)
        observed_at = thread.decided_at or thread.created_at
        cluster = clusters.setdefault(
            key,
            {"direction": direction, "label": category, "evidence_ids": set(), "first_observed_at": observed_at},
        )
        cluster["evidence_ids"].add(thread.id)
        cluster["label"] = category  # keep the most recently seen phrasing
        if observed_at < cluster["first_observed_at"]:
            cluster["first_observed_at"] = observed_at

    return [c for c in clusters.values() if len(c["evidence_ids"]) >= MIN_LEARNING_EVIDENCE]


def _commercial_category_key(direction: str, category_norm: str) -> str:
    """Parallel to _category_key's `performance/...` convention — the
    `commercial/...` prefix is what lets the Analytics learnings list (and
    any future filter) distinguish the two loops while sharing one table."""
    return f"commercial/{direction}/{category_norm.replace(' ', '_')}"


def _commercial_statement(direction: str, label: str, count: int) -> str:
    verb = "successful" if direction == "positive" else "declined"
    return f"{label.strip().capitalize()} brand partnerships appear associated with {verb} outcomes (seen across {count} deals)."


async def sync_commercial_learnings(db: AsyncSession, *, creator_id: str) -> list[StrategicLearning]:
    """Commercial-loop analog of sync_learnings (see _upsert_learning_clusters
    for the shared persistence discipline). Confidence here has no per-item
    factor-confidence component to average in (unlike performance learnings'
    diagnosis-reported per-factor read) — it's evidence-count only, same
    discipline as BaseAgent._coverage_confidence elsewhere: more
    corroborating deals is the only thing that earns higher confidence."""
    candidates = await collect_commercial_learning_candidates(db, creator_id=creator_id)
    return await _upsert_learning_clusters(
        db,
        creator_id=creator_id,
        candidates=candidates,
        category_fn=lambda c: _commercial_category_key(c["direction"], _normalize_factor(c["label"])),
        statement_fn=lambda c: _commercial_statement(c["direction"], c["label"], len(c["evidence_ids"])),
        confidence_fn=lambda c: _EVIDENCE_COUNT_WEIGHT.get(len(c["evidence_ids"]), _EVIDENCE_COUNT_WEIGHT_CAP),
        scope_fn=lambda c: "creator-wide",
    )


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
