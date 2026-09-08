from datetime import datetime, timezone

import pytest

from app.agent_service.agents.creator_intelligence import CreatorIntelligenceAgent
from app.agent_service.model_router.router import ModelResponse
from app.schemas.creator import CreatorRead, CreatorStateSnapshot


@pytest.fixture
def build_snapshot():
    def _build(**overrides) -> CreatorStateSnapshot:
        now = datetime.now(timezone.utc)
        creator = CreatorRead(
            id="cr_test",
            name="Test Creator",
            niche="AI tools",
            onboarding_status="created",
            created_at=now,
            updated_at=now,
        )
        return CreatorStateSnapshot(creator=creator, **overrides)

    return _build


def test_parse_json_accepts_plain_json():
    data = CreatorIntelligenceAgent._parse_json(
        '{"positioning_statement": "x", "expertise": ["a"], "bio": "b"}',
        required_key="positioning_statement",
    )
    assert data["positioning_statement"] == "x"


def test_parse_json_strips_markdown_fences():
    text = '```json\n{"positioning_statement": "x", "expertise": [], "bio": "b"}\n```'
    data = CreatorIntelligenceAgent._parse_json(text, required_key="positioning_statement")
    assert data["positioning_statement"] == "x"


def test_parse_json_raises_on_invalid_json():
    with pytest.raises(ValueError):
        CreatorIntelligenceAgent._parse_json("not json at all", required_key="positioning_statement")


def test_parse_json_raises_when_missing_required_field():
    with pytest.raises(ValueError):
        CreatorIntelligenceAgent._parse_json('{"expertise": ["a"]}', required_key="positioning_statement")


def test_parse_json_checks_caller_specified_key():
    with pytest.raises(ValueError):
        CreatorIntelligenceAgent._parse_json('{"positioning_statement": "x"}', required_key="tone")


def test_fallback_positioning_includes_niche_in_statement():
    data = CreatorIntelligenceAgent._fallback_positioning("Alice", "AI tools", None)
    assert "AI tools" in data["positioning_statement"]
    assert data["expertise"] == ["AI tools"]


class _FakeModelRouter:
    """Simulates a live (non-stub) model response so the JSON-parsing path
    that will run for real once ANTHROPIC_API_KEY is set gets exercised now,
    not just discovered the first time someone adds a key."""

    def __init__(self, text: str):
        self._text = text

    async def complete(self, **kwargs):
        return ModelResponse(
            text=self._text, model="fake", input_tokens=1, output_tokens=1, latency_ms=1, stub=False
        )


async def test_analyze_voice_parses_live_model_json_and_cites_evidence():
    agent = CreatorIntelligenceAgent()
    router = _FakeModelRouter(
        '{"tone": "direct", "sentence_style": "short", "pacing": "fast", '
        '"personality": "blunt", "humor_level": "dry", "storytelling_style": "anecdotal", '
        '"opinion_style": "assertive", "signature_phrases": ["let\'s go"], "cta_style": "direct ask"}'
    )
    transcripts = [{"id": "cnt_abc123", "title": "Post 1", "transcript": "some script text"}]

    output = await agent._analyze_voice(transcripts, router)

    assert output.status == "success"
    assert output.evidence_ids == ["cnt_abc123"]
    change = output.proposed_state_changes[0]
    assert change["type"] == "voice_profile_upsert"
    assert change["data"]["tone"] == "direct"
    assert change["evidence_ids"] == ["cnt_abc123"]


async def test_analyze_voice_fails_safely_on_bad_json():
    agent = CreatorIntelligenceAgent()
    router = _FakeModelRouter("not valid json")
    transcripts = [{"id": "cnt_abc123", "title": "Post 1", "transcript": "some script text"}]

    output = await agent._analyze_voice(transcripts, router)

    assert output.status == "failed"
    assert output.proposed_state_changes == []


class _RoutingFakeModelRouter:
    """Returns different canned text depending on which sub-job's prompt is
    calling — lets a test drive positioning and voice to different outcomes
    in the same run() call, which a single-response fake can't do."""

    def __init__(self, *, positioning_text: str, voice_text: str):
        self._positioning_text = positioning_text
        self._voice_text = voice_text

    async def complete(self, *, system, **kwargs):
        text = self._voice_text if "Infer their voice" in system else self._positioning_text
        return ModelResponse(text=text, model="fake", input_tokens=1, output_tokens=1, latency_ms=1, stub=False)


async def test_run_reports_partial_when_only_one_subjob_fails(build_snapshot):
    """Regression test: a positioning-only failure must not be reported as
    overall 'success' just because voice succeeded alongside it — that would
    silently drop the failed sub-job (and its state change) with no signal."""
    agent = CreatorIntelligenceAgent()
    router = _RoutingFakeModelRouter(
        positioning_text="not valid json",
        voice_text='{"tone": "direct", "sentence_style": "short", "pacing": "fast", '
        '"personality": "blunt", "humor_level": "dry", "storytelling_style": "anecdotal", '
        '"opinion_style": "assertive", "signature_phrases": [], "cta_style": "direct ask"}',
    )
    transcripts = [{"id": "cnt_abc123", "title": "Post 1", "transcript": "some script text"}]

    output = await agent.run(build_snapshot(), router, voice_transcripts=transcripts)

    assert output.status == "partial"
    assert len(output.proposed_state_changes) == 1
    assert output.proposed_state_changes[0]["type"] == "voice_profile_upsert"
    assert any("positioning" in w.lower() or "invalid json" in w.lower() for w in output.warnings)
