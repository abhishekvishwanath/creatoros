from datetime import datetime, timezone

import pytest

from app.agent_service.agents.strategy_engine import StrategyEngineAgent
from app.agent_service.model_router.router import ModelResponse
from app.schemas.creator import CreatorRead, CreatorStateSnapshot


@pytest.fixture
def build_snapshot():
    def _build(**overrides) -> CreatorStateSnapshot:
        now = datetime.now(timezone.utc)
        creator = CreatorRead(
            id="cr_test",
            name="Test Creator",
            niche="personal finance",
            onboarding_status="created",
            created_at=now,
            updated_at=now,
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
        raise RuntimeError("Error code: 429 - Too Many Requests")


async def test_run_without_opportunities_skips_without_calling_model(build_snapshot):
    agent = StrategyEngineAgent()
    output = await agent.run(build_snapshot(), _RaisingModelRouter(), available_opportunities=[])

    assert output.status == "success"
    assert output.proposed_state_changes == []
    assert output.confidence == 0.0


async def test_run_parses_live_model_json_and_grounds_items(build_snapshot):
    agent = StrategyEngineAgent()
    router = _FakeModelRouter(
        '{"summary": "A mix of authority and reach content this week.", '
        '"items": [{"opportunity_id": "opp_1", "day_of_week": 0, "portfolio_role": "authority"}, '
        '{"opportunity_id": "opp_2", "day_of_week": 2, "portfolio_role": "reach"}]}'
    )
    opportunities = [
        {"id": "opp_1", "topic": "budgeting", "subtopic": None, "format": None, "score": 0.8},
        {"id": "opp_2", "topic": "taxes", "subtopic": None, "format": None, "score": 0.6},
    ]

    output = await agent.run(build_snapshot(), router, available_opportunities=opportunities)

    assert output.status == "success"
    change = output.proposed_state_changes[0]
    assert change["type"] == "strategy_upsert"
    assert len(change["data"]["items"]) == 2
    assert set(output.evidence_ids) == {"opp_1", "opp_2"}
    # coverage = 2/2 -> confidence = min(0.3 + 0.3*1, 0.6) = 0.6
    assert change["confidence"] == 0.6


async def test_run_drops_items_with_hallucinated_opportunity_id(build_snapshot):
    agent = StrategyEngineAgent()
    router = _FakeModelRouter(
        '{"summary": "s", "items": [{"opportunity_id": "opp_does_not_exist", "day_of_week": 0, "portfolio_role": "reach"}]}'
    )
    opportunities = [{"id": "opp_1", "topic": "budgeting", "subtopic": None, "format": None, "score": 0.8}]

    output = await agent.run(build_snapshot(), router, available_opportunities=opportunities)

    assert output.status == "success"
    assert output.proposed_state_changes == []
    assert any("dropped" in w.lower() for w in output.warnings)


async def test_run_keeps_only_the_first_item_on_a_day_collision(build_snapshot):
    """Regression test: the system prompt asks for at most one opportunity
    per day, but nothing stops the model from double-booking a day anyway.
    The calendar view is keyed by day_of_week, so a silently-inserted second
    item on the same day would have its opportunity marked "used" on
    activation while never appearing anywhere in the UI."""
    agent = StrategyEngineAgent()
    router = _FakeModelRouter(
        '{"summary": "s", "items": ['
        '{"opportunity_id": "opp_1", "day_of_week": 0, "portfolio_role": "reach"}, '
        '{"opportunity_id": "opp_2", "day_of_week": 0, "portfolio_role": "authority"}]}'
    )
    opportunities = [
        {"id": "opp_1", "topic": "budgeting", "subtopic": None, "format": None, "score": 0.8},
        {"id": "opp_2", "topic": "taxes", "subtopic": None, "format": None, "score": 0.6},
    ]

    output = await agent.run(build_snapshot(), router, available_opportunities=opportunities)

    change = output.proposed_state_changes[0]
    assert len(change["data"]["items"]) == 1
    assert change["data"]["items"][0]["opportunity_id"] == "opp_1"
    assert any("dropped" in w.lower() for w in output.warnings)


async def test_run_drops_items_with_invalid_role_or_day(build_snapshot):
    agent = StrategyEngineAgent()
    router = _FakeModelRouter(
        '{"summary": "s", "items": ['
        '{"opportunity_id": "opp_1", "day_of_week": 9, "portfolio_role": "reach"}, '
        '{"opportunity_id": "opp_1", "day_of_week": 0, "portfolio_role": "made_up_role"}]}'
    )
    opportunities = [{"id": "opp_1", "topic": "budgeting", "subtopic": None, "format": None, "score": 0.8}]

    output = await agent.run(build_snapshot(), router, available_opportunities=opportunities)

    assert output.status == "success"
    assert output.proposed_state_changes == []


async def test_run_fails_safely_on_bad_json(build_snapshot):
    agent = StrategyEngineAgent()
    router = _FakeModelRouter("not valid json")
    opportunities = [{"id": "opp_1", "topic": "budgeting", "subtopic": None, "format": None, "score": 0.8}]

    output = await agent.run(build_snapshot(), router, available_opportunities=opportunities)

    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_run_survives_model_call_raising(build_snapshot):
    agent = StrategyEngineAgent()
    opportunities = [{"id": "opp_1", "topic": "budgeting", "subtopic": None, "format": None, "score": 0.8}]

    output = await agent.run(build_snapshot(), _RaisingModelRouter(), available_opportunities=opportunities)

    assert output.status == "failed"
    assert any("429" in w or "Too Many Requests" in w for w in output.warnings)
