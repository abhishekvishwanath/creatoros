from datetime import datetime, timezone

import pytest

from app.agent_service.agents.performance_intelligence import PerformanceIntelligenceAgent
from app.agent_service.model_router.router import ModelResponse
from app.schemas.creator import CreatorRead, CreatorStateSnapshot


@pytest.fixture
def build_snapshot():
    def _build(**overrides) -> CreatorStateSnapshot:
        now = datetime.now(timezone.utc)
        creator = CreatorRead(
            id="cr_test", name="Test Creator", niche="finance", onboarding_status="created", created_at=now, updated_at=now
        )
        return CreatorStateSnapshot(creator=creator, **overrides)

    return _build


class _FakeModelRouter:
    def __init__(self, text: str):
        self._text = text

    async def complete(self, **kwargs):
        return ModelResponse(text=self._text, model="fake", input_tokens=1, output_tokens=1, latency_ms=1, stub=False)


class _RaisingModelRouter:
    async def complete(self, **kwargs):
        raise RuntimeError("boom")


DIAGNOSIS_JSON = (
    '{"summary": "This piece outperformed the creator\'s baseline.", '
    '"associated_factors": [{"factor": "contrarian hook", "confidence": "medium", '
    '"note": "appears associated with stronger early retention"}], '
    '"next_test": "Try another contrarian hook next week.", "confidence": "medium"}'
)


async def test_run_parses_diagnosis_with_ratios_present(build_snapshot):
    agent = PerformanceIntelligenceAgent()
    router = _FakeModelRouter(DIAGNOSIS_JSON)
    content_item = {"id": "cnt_1", "topic": "budgeting", "format": "short"}
    snapshot = {"views": 8000}
    baselines = {"views": {"overall": {"median": 3800, "sample_size": 5}}}
    ratios = {"views_vs_overall_median": 2.1}

    output = await agent.run(
        build_snapshot(), router, content_item=content_item, snapshot=snapshot, baselines=baselines, ratios=ratios
    )

    assert output.status == "success"
    change = output.proposed_state_changes[0]
    assert change["type"] == "performance_diagnosis"
    assert change["data"]["associated_factors"][0]["factor"] == "contrarian hook"
    assert output.next_action == "Try another contrarian hook next week."


async def test_run_skips_without_ratios_rather_than_guessing(build_snapshot):
    """Regression guard: with no baseline to compare against, the agent must
    not call the model and improvise a diagnosis anyway (CLAUDE.md §19 — a
    thin/absent sample isn't grounds for a confident-sounding read)."""
    agent = PerformanceIntelligenceAgent()
    router = _FakeModelRouter(DIAGNOSIS_JSON)
    content_item = {"id": "cnt_1", "topic": "budgeting", "format": "short"}

    output = await agent.run(build_snapshot(), router, content_item=content_item, snapshot={"views": 100}, ratios={})

    assert output.status == "success"
    assert output.proposed_state_changes == []
    assert output.confidence == 0.0


async def test_run_proceeds_when_baselines_exist_even_if_ratios_is_empty(build_snapshot):
    """Regression guard: a zero-median baseline (e.g. a creator whose posts
    typically get 0 saves) produces no ratio (division by zero is
    undefined) even though real baseline history exists. The gate must key
    off `baselines`, not `ratios`, or this case gets misreported as 'not
    enough history' when it's actually just an unrepresentable ratio."""
    agent = PerformanceIntelligenceAgent()
    router = _FakeModelRouter(DIAGNOSIS_JSON)
    content_item = {"id": "cnt_1", "topic": "budgeting", "format": "short"}
    baselines = {"saves": {"overall": {"median": 0, "sample_size": 5}}}

    output = await agent.run(
        build_snapshot(), router, content_item=content_item, snapshot={"saves": 50}, baselines=baselines, ratios={}
    )

    assert output.status == "success"
    assert output.proposed_state_changes != []


async def test_run_fails_safely_on_bad_json(build_snapshot):
    agent = PerformanceIntelligenceAgent()
    router = _FakeModelRouter("not valid json")
    content_item = {"id": "cnt_1", "topic": "budgeting", "format": "short"}

    output = await agent.run(
        build_snapshot(),
        router,
        content_item=content_item,
        snapshot={"views": 8000},
        baselines={"views": {"overall": {"median": 3800, "sample_size": 5}}},
        ratios={"views_vs_overall_median": 2.1},
    )

    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_run_survives_model_call_raising(build_snapshot):
    agent = PerformanceIntelligenceAgent()
    content_item = {"id": "cnt_1", "topic": "budgeting", "format": "short"}

    output = await agent.run(
        build_snapshot(),
        _RaisingModelRouter(),
        content_item=content_item,
        snapshot={"views": 8000},
        baselines={"views": {"overall": {"median": 3800, "sample_size": 5}}},
        ratios={"views_vs_overall_median": 2.1},
    )

    assert output.status == "failed"
