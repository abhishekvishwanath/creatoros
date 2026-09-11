import pytest

from app.domain.content.models import ContentItem
from app.domain.creator.models import Creator, User
from app.domain.experiments.models import ExperimentResult, StrategicLearning
from app.domain.experiments.service import (
    add_experiment_result,
    apply_experiment_evaluation,
    compute_experiment_stats,
    create_experiment,
    get_experiment,
    list_experiment_results,
    list_experiments,
    set_experiment_status,
)
from app.infrastructure.db.session import AsyncSessionLocal
from sqlalchemy import select

_creator_counter = 0


async def _make_creator() -> str:
    global _creator_counter
    _creator_counter += 1
    async with AsyncSessionLocal() as session:
        user = User(email=f"experiment{_creator_counter}@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Experiment Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def test_create_and_get_experiment():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        experiment = await create_experiment(
            session, creator_id=creator_id, hypothesis="Contrarian hooks improve retention.", variable="hook_type"
        )
        await session.commit()
        experiment_id = experiment.id

    async with AsyncSessionLocal() as session:
        fetched = await get_experiment(session, creator_id=creator_id, experiment_id=experiment_id)
    assert fetched.hypothesis == "Contrarian hooks improve retention."
    assert fetched.status == "planned"


async def test_list_experiments_returns_only_this_creators():
    creator_id = await _make_creator()
    other_creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await create_experiment(session, creator_id=creator_id, hypothesis="h1")
        await create_experiment(session, creator_id=other_creator_id, hypothesis="h2")
        await session.commit()

    async with AsyncSessionLocal() as session:
        experiments = await list_experiments(session, creator_id=creator_id)
    assert len(experiments) == 1
    assert experiments[0].hypothesis == "h1"


async def test_set_experiment_status_valid_transition():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        experiment = await create_experiment(session, creator_id=creator_id, hypothesis="h")
        await session.commit()
        experiment = await get_experiment(session, creator_id=creator_id, experiment_id=experiment.id)
        updated = await set_experiment_status(session, experiment=experiment, status="running")
        await session.commit()
    assert updated.status == "running"


async def test_set_experiment_status_rejects_invalid_transition():
    """A completed experiment can't be moved back to "running" — mirrors
    app/domain/content/service.py::mark_content_stage's contract that an
    invalid transition raises rather than silently no-op'ing."""
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        experiment = await create_experiment(session, creator_id=creator_id, hypothesis="h")
        await session.commit()
        experiment = await get_experiment(session, creator_id=creator_id, experiment_id=experiment.id)
        await set_experiment_status(session, experiment=experiment, status="completed")
        await session.commit()
        with pytest.raises(ValueError):
            await set_experiment_status(session, experiment=experiment, status="running")


async def test_compute_experiment_stats_requires_both_groups_adequate():
    results = [
        ExperimentResult(id="er1", experiment_id="exp1", metric_name="retention", metric_value=40.0, group="test"),
        ExperimentResult(id="er2", experiment_id="exp1", metric_name="retention", metric_value=42.0, group="test"),
        ExperimentResult(id="er3", experiment_id="exp1", metric_name="retention", metric_value=30.0, group="control"),
    ]
    stats = compute_experiment_stats(results)
    assert stats["retention"]["test_n"] == 2
    assert stats["retention"]["control_n"] == 1
    assert stats["retention"]["adequate_evidence"] is False


async def test_compute_experiment_stats_computes_delta_when_adequate():
    results = [
        ExperimentResult(id="er1", experiment_id="exp1", metric_name="retention", metric_value=40.0, group="test"),
        ExperimentResult(id="er2", experiment_id="exp1", metric_name="retention", metric_value=44.0, group="test"),
        ExperimentResult(id="er3", experiment_id="exp1", metric_name="retention", metric_value=30.0, group="control"),
        ExperimentResult(id="er4", experiment_id="exp1", metric_name="retention", metric_value=32.0, group="control"),
    ]
    stats = compute_experiment_stats(results)
    entry = stats["retention"]
    assert entry["adequate_evidence"] is True
    assert entry["test_median"] == 42.0
    assert entry["control_median"] == 31.0
    assert entry["delta"] == pytest.approx(11.0)


async def test_apply_experiment_evaluation_retains_hypothesis_creates_learning():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        experiment = await create_experiment(session, creator_id=creator_id, hypothesis="Contrarian hooks help.")
        session.add_all(
            [ContentItem(id=f"cnt_{i}", creator_id=creator_id, topic="budgeting") for i in range(1, 5)]
        )
        await session.commit()
        experiment_id = experiment.id

    async with AsyncSessionLocal() as session:
        await add_experiment_result(
            session, experiment_id=experiment_id, content_item_id="cnt_1", metric_name="retention", metric_value=40.0, group="test"
        )
        await add_experiment_result(
            session, experiment_id=experiment_id, content_item_id="cnt_2", metric_name="retention", metric_value=44.0, group="test"
        )
        await add_experiment_result(
            session, experiment_id=experiment_id, content_item_id="cnt_3", metric_name="retention", metric_value=30.0, group="control"
        )
        await add_experiment_result(
            session, experiment_id=experiment_id, content_item_id="cnt_4", metric_name="retention", metric_value=32.0, group="control"
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        experiment = await get_experiment(session, creator_id=creator_id, experiment_id=experiment_id)
        results = await list_experiment_results(session, experiment_id=experiment_id)
        stats = compute_experiment_stats(results)
        await apply_experiment_evaluation(
            session,
            experiment=experiment,
            data={
                "conclusion": "Contrarian hooks appear to improve retention.",
                "confidence": "medium",
                "next_action": "Test on more posts.",
                "retain_hypothesis": True,
            },
            stats=stats,
            results=results,
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        experiment = await get_experiment(session, creator_id=creator_id, experiment_id=experiment_id)
        result = await session.execute(
            select(StrategicLearning).where(
                StrategicLearning.creator_id == creator_id, StrategicLearning.category == f"experiment/{experiment_id}"
            )
        )
        learning = result.scalar_one()

    assert experiment.status == "completed"
    assert experiment.conclusion == "Contrarian hooks appear to improve retention."
    assert learning.statement == "Contrarian hooks appear to improve retention."
    assert learning.scope == "temporary experiment"
    assert sorted(learning.evidence_ids) == ["cnt_1", "cnt_2", "cnt_3", "cnt_4"]


async def test_apply_experiment_evaluation_rejected_hypothesis_creates_no_learning():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        experiment = await create_experiment(session, creator_id=creator_id, hypothesis="Longer intros help.")
        await session.commit()
        experiment_id = experiment.id

    async with AsyncSessionLocal() as session:
        experiment = await get_experiment(session, creator_id=creator_id, experiment_id=experiment_id)
        await apply_experiment_evaluation(
            session,
            experiment=experiment,
            data={"conclusion": "No clear effect.", "confidence": "low", "next_action": None, "retain_hypothesis": False},
            stats={},
            results=[],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(StrategicLearning).where(
                StrategicLearning.creator_id == creator_id, StrategicLearning.category == f"experiment/{experiment_id}"
            )
        )
        learning = result.scalar_one_or_none()
    assert learning is None
