from datetime import datetime, timezone

import pytest

from app.agent_service.agents.audience_intelligence import AudienceIntelligenceAgent
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


class _RoutingFakeModelRouter:
    def __init__(self, *, profile_text: str, segments_text: str):
        self._profile_text = profile_text
        self._segments_text = segments_text

    async def complete(self, *, system, **kwargs):
        text = self._segments_text if "Identify 1 to 4 audience segments" in system else self._profile_text
        return ModelResponse(text=text, model="fake", input_tokens=1, output_tokens=1, latency_ms=1, stub=False)


class _RaisingModelRouter:
    async def complete(self, **kwargs):
        raise RuntimeError("Error code: 429 - Too Many Requests")


async def test_run_without_signals_skips_without_calling_model(build_snapshot):
    agent = AudienceIntelligenceAgent()
    output = await agent.run(build_snapshot(), _RaisingModelRouter(), audience_signals=[])

    assert output.status == "success"
    assert output.proposed_state_changes == []
    assert output.confidence == 0.0


async def test_profile_only_runs_below_segment_minimum(build_snapshot):
    agent = AudienceIntelligenceAgent()
    router = _FakeModelRouter(
        '{"geography": null, "demographics": null, "psychographics": null, '
        '"knowledge_level": "beginner", "purchase_intent": "medium", "preferred_language": null}'
    )
    signals = [{"id": "asig_1", "text": "How do I even start budgeting?", "source_platform": "instagram"}]

    output = await agent.run(build_snapshot(), router, audience_signals=signals)

    assert output.status == "success"
    change_types = {c["type"] for c in output.proposed_state_changes}
    assert change_types == {"audience_profile_upsert"}


async def test_run_includes_segments_when_enough_signals(build_snapshot):
    agent = AudienceIntelligenceAgent()
    router = _RoutingFakeModelRouter(
        profile_text='{"geography": null, "demographics": null, "psychographics": null, '
        '"knowledge_level": "beginner", "purchase_intent": "medium", "preferred_language": null}',
        segments_text='{"segments": [{"name": "Budgeting beginners", "problems": ["no system"], '
        '"desires": [], "objections": [], "questions": [], "fears": [], "aspirations": [], '
        '"language": [], "knowledge_level": "beginner", "signal_ids": ["asig_1", "asig_2"]}]}',
    )
    signals = [
        {"id": "asig_1", "text": "How do I start budgeting?", "source_platform": None},
        {"id": "asig_2", "text": "What app should I use to budget?", "source_platform": None},
        {"id": "asig_3", "text": "I never know where my money goes.", "source_platform": None},
    ]

    output = await agent.run(build_snapshot(), router, audience_signals=signals)

    assert output.status == "success"
    change_types = {c["type"] for c in output.proposed_state_changes}
    assert change_types == {"audience_profile_upsert", "audience_segments_upsert"}


async def test_analyze_segments_drops_segments_citing_no_real_signal_id(build_snapshot):
    agent = AudienceIntelligenceAgent()
    router = _FakeModelRouter('{"segments": [{"name": "made up", "signal_ids": ["asig_fake"]}]}')
    signals = [
        {"id": "asig_1", "text": "a", "source_platform": None},
        {"id": "asig_2", "text": "b", "source_platform": None},
        {"id": "asig_3", "text": "c", "source_platform": None},
    ]

    output = await agent._analyze_segments(signals, router)

    assert output.status == "success"
    assert output.proposed_state_changes == []
    assert any("dropped" in w.lower() for w in output.warnings)


async def test_analyze_segments_filters_partial_hallucinated_ids():
    agent = AudienceIntelligenceAgent()
    router = _FakeModelRouter(
        '{"segments": [{"name": "real", "signal_ids": ["asig_1", "asig_fake"]}]}'
    )
    signals = [
        {"id": "asig_1", "text": "a", "source_platform": None},
        {"id": "asig_2", "text": "b", "source_platform": None},
        {"id": "asig_3", "text": "c", "source_platform": None},
    ]

    output = await agent._analyze_segments(signals, router)

    change = output.proposed_state_changes[0]
    assert change["data"]["segments"][0]["evidence_ids"] == ["asig_1"]


async def test_analyze_segments_survives_a_literal_null_segments_value():
    """Regression test: a model responding with well-formed JSON whose
    "segments" value is a literal null (a plausible "found nothing" answer)
    must degrade to zero segments, not crash — `.get("segments", [])`'s
    default only applies when the key is absent, not when it's null."""
    agent = AudienceIntelligenceAgent()
    router = _FakeModelRouter('{"segments": null}')
    signals = [
        {"id": "asig_1", "text": "a", "source_platform": None},
        {"id": "asig_2", "text": "b", "source_platform": None},
        {"id": "asig_3", "text": "c", "source_platform": None},
    ]

    output = await agent._analyze_segments(signals, router)

    assert output.status == "success"
    assert output.proposed_state_changes == []


async def test_analyze_profile_fails_safely_on_bad_json(build_snapshot):
    agent = AudienceIntelligenceAgent()
    router = _FakeModelRouter("not valid json")
    signals = [{"id": "asig_1", "text": "a", "source_platform": None}]

    output = await agent._analyze_profile(build_snapshot(), signals, router)

    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_run_survives_model_call_raising(build_snapshot):
    agent = AudienceIntelligenceAgent()
    signals = [{"id": "asig_1", "text": "a", "source_platform": None}]

    output = await agent.run(build_snapshot(), _RaisingModelRouter(), audience_signals=signals)

    assert output.status == "failed"
    assert any("429" in w or "Too Many Requests" in w for w in output.warnings)
