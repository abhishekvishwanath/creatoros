from datetime import datetime, timezone

import pytest

from app.agent_service.agents.trend_intelligence import TrendIntelligenceAgent
from app.agent_service.model_router.router import ModelResponse
from app.schemas.creator import CreatorRead, CreatorStateSnapshot


@pytest.fixture
def build_snapshot():
    def _build(**overrides) -> CreatorStateSnapshot:
        now = datetime.now(timezone.utc)
        creator = CreatorRead(
            id="cr_test", name="Test Creator", niche="personal finance", onboarding_status="created",
            created_at=now, updated_at=now,
        )
        return CreatorStateSnapshot(creator=creator, **overrides)

    return _build


class _FakeModelRouter:
    def __init__(self, text: str):
        self._text = text

    async def complete(self, **kwargs):
        return ModelResponse(text=self._text, model="fake", input_tokens=1, output_tokens=1, latency_ms=1, stub=False)


class _StubModelRouter:
    async def complete(self, **kwargs):
        return ModelResponse(text="STUB RESPONSE", model="stub:none", input_tokens=0, output_tokens=0, latency_ms=0, stub=True)


class _RaisingModelRouter:
    async def complete(self, **kwargs):
        raise RuntimeError("Error code: 429 - Too Many Requests")


class _SpyModelRouter:
    def __init__(self, text: str):
        self._text = text
        self.last_kwargs: dict = {}

    async def complete(self, **kwargs):
        self.last_kwargs = kwargs
        return ModelResponse(text=self._text, model="fake", input_tokens=1, output_tokens=1, latency_ms=1, stub=False)


TOPICS = [
    {
        "topic_key": "ai productivity",
        "topic": "AI productivity",
        "signal_count": 4,
        "recent_signal_count": 3,
        "momentum": "rising",
        "summaries": ["A competitor's AI workflow video got unusually high saves."],
    }
]

INSIGHTS_JSON = (
    '{"insights": [{"topic_key": "ai productivity", "saturation_estimate": "medium", '
    '"durability": "durable", "relevance_to_creator": "high", '
    '"reasoning": "Fits the creator\'s pillar and audience.", "confidence": "medium"}]}'
)


async def test_run_skips_with_no_topics(build_snapshot):
    agent = TrendIntelligenceAgent()
    output = await agent.run(build_snapshot(), _FakeModelRouter(INSIGHTS_JSON), topics=[])
    assert output.status == "success"
    assert output.proposed_state_changes == []
    assert any("research signals" in w.lower() for w in output.warnings)


async def test_run_parses_live_model_json(build_snapshot):
    agent = TrendIntelligenceAgent()
    output = await agent.run(build_snapshot(), _FakeModelRouter(INSIGHTS_JSON), topics=TOPICS)
    assert output.status == "success"
    change = output.proposed_state_changes[0]
    assert change["type"] == "trend_insights"
    assert change["data"]["insights"][0]["topic_key"] == "ai productivity"
    assert output.warnings == []


async def test_run_drops_insight_for_topic_not_given(build_snapshot):
    agent = TrendIntelligenceAgent()
    hallucinated = (
        '{"insights": [{"topic_key": "made up topic", "saturation_estimate": "low", '
        '"durability": "durable", "relevance_to_creator": "high", "reasoning": "x", "confidence": "low"}]}'
    )
    output = await agent.run(build_snapshot(), _FakeModelRouter(hallucinated), topics=TOPICS)
    assert output.proposed_state_changes[0]["data"]["insights"] == []
    assert any("not given" in w for w in output.warnings)


async def test_run_skips_in_stub_mode_rather_than_guessing(build_snapshot):
    agent = TrendIntelligenceAgent()
    output = await agent.run(build_snapshot(), _StubModelRouter(), topics=TOPICS)
    assert output.status == "success"
    assert output.proposed_state_changes == []
    assert any("skipped" in w.lower() for w in output.warnings)


async def test_run_fails_safely_on_bad_json(build_snapshot):
    agent = TrendIntelligenceAgent()
    output = await agent.run(build_snapshot(), _FakeModelRouter("not valid json"), topics=TOPICS)
    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_run_survives_model_call_raising(build_snapshot):
    agent = TrendIntelligenceAgent()
    output = await agent.run(build_snapshot(), _RaisingModelRouter(), topics=TOPICS)
    assert output.status == "failed"
    assert any("429" in w or "Too Many Requests" in w for w in output.warnings)


async def test_run_includes_topic_stats_in_prompt(build_snapshot):
    agent = TrendIntelligenceAgent()
    router = _SpyModelRouter(INSIGHTS_JSON)
    await agent.run(build_snapshot(), router, topics=TOPICS)
    assert "ai productivity" in router.last_kwargs["user"]
    assert "rising" in router.last_kwargs["user"]
