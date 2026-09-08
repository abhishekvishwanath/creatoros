from datetime import datetime, timezone

import pytest

from app.agent_service.agents.opportunity_engine import OpportunityEngineAgent
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


async def test_run_without_signals_skips_without_calling_model(build_snapshot):
    agent = OpportunityEngineAgent()
    output = await agent.run(build_snapshot(), _RaisingModelRouter(), research_signals=[])

    assert output.status == "success"
    assert output.proposed_state_changes == []
    assert output.confidence == 0.0


async def test_run_parses_live_model_json_and_cites_evidence(build_snapshot):
    agent = OpportunityEngineAgent()
    router = _FakeModelRouter(
        '{"opportunities": [{"topic": "budgeting", "subtopic": "envelope method", '
        '"angle": "why it still works", "format": "short-form video", '
        '"content_pillar_name": null, '
        '"score_components": {"audience_fit": 0.8, "creator_fit": 0.7, "demand": 0.6, '
        '"novelty": 0.5, "evidence": 0.9}, "competition_level": "medium", '
        '"saturation_estimate": "low", "production_complexity": "low", '
        '"recommended_time_window": "this week", "evidence_signal_ids": ["sig_1"]}]}'
    )
    signals = [{"id": "sig_1", "topic": "budgeting", "subtopic": None, "format": None, "platform": "instagram", "summary": "x"}]

    output = await agent.run(build_snapshot(), router, research_signals=signals)

    assert output.status == "success"
    assert output.evidence_ids == ["sig_1"]
    change = output.proposed_state_changes[0]
    assert change["type"] == "opportunities_upsert"
    assert change["data"]["opportunities"][0]["topic"] == "budgeting"
    # coverage = 1/1 -> confidence = min(0.3 + 0.3*1, 0.6) = 0.6
    assert change["confidence"] == 0.6


async def test_run_strips_hallucinated_ids_from_a_partially_grounded_opportunity(build_snapshot):
    """Regression test: an opportunity citing one real id and one the model
    made up must keep the real id but drop the fake one, not pass the fake id
    through to apply_opportunities where it would violate the
    research_signals foreign key on write."""
    agent = OpportunityEngineAgent()
    router = _FakeModelRouter(
        '{"opportunities": [{"topic": "budgeting", '
        '"evidence_signal_ids": ["sig_1", "sig_does_not_exist"]}]}'
    )
    signals = [{"id": "sig_1", "topic": "budgeting", "subtopic": None, "format": None, "platform": None, "summary": "x"}]

    output = await agent.run(build_snapshot(), router, research_signals=signals)

    assert output.status == "success"
    change = output.proposed_state_changes[0]
    assert change["data"]["opportunities"][0]["evidence_signal_ids"] == ["sig_1"]
    assert output.evidence_ids == ["sig_1"]


async def test_run_drops_opportunities_that_cite_no_real_signal_id(build_snapshot):
    agent = OpportunityEngineAgent()
    router = _FakeModelRouter(
        '{"opportunities": [{"topic": "made up", "evidence_signal_ids": ["sig_does_not_exist"]}]}'
    )
    signals = [{"id": "sig_1", "topic": "budgeting", "subtopic": None, "format": None, "platform": None, "summary": "x"}]

    output = await agent.run(build_snapshot(), router, research_signals=signals)

    assert output.status == "success"
    assert output.proposed_state_changes == []
    assert any("dropped" in w.lower() for w in output.warnings)


async def test_run_fails_safely_on_bad_json(build_snapshot):
    agent = OpportunityEngineAgent()
    router = _FakeModelRouter("not valid json")
    signals = [{"id": "sig_1", "topic": "budgeting", "subtopic": None, "format": None, "platform": None, "summary": "x"}]

    output = await agent.run(build_snapshot(), router, research_signals=signals)

    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_run_survives_model_call_raising(build_snapshot):
    agent = OpportunityEngineAgent()
    signals = [{"id": "sig_1", "topic": "budgeting", "subtopic": None, "format": None, "platform": None, "summary": "x"}]

    output = await agent.run(build_snapshot(), _RaisingModelRouter(), research_signals=signals)

    assert output.status == "failed"
    assert any("429" in w or "Too Many Requests" in w for w in output.warnings)
