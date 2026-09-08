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


async def test_analyze_pillars_parses_live_model_json_and_cites_evidence():
    agent = CreatorIntelligenceAgent()
    router = _FakeModelRouter(
        '{"pillars": [{"name": "Budgeting basics", "description": "Beginner money management", '
        '"content_ids": ["cnt_1", "cnt_2"]}]}'
    )
    content = [
        {"id": "cnt_1", "title": "Post 1", "transcript": "budgeting tips"},
        {"id": "cnt_2", "title": "Post 2", "transcript": "more budgeting tips"},
        {"id": "cnt_3", "title": "Post 3", "transcript": "unrelated"},
    ]

    output = await agent._analyze_pillars(content, router)

    assert output.status == "success"
    assert output.evidence_ids == ["cnt_1", "cnt_2", "cnt_3"]
    change = output.proposed_state_changes[0]
    assert change["type"] == "content_pillars_upsert"
    assert change["data"]["pillars"][0]["name"] == "Budgeting basics"
    # coverage = 2/3 cited -> confidence = min(0.3 + 0.3*0.667, 0.6) = 0.5
    assert change["confidence"] == 0.5


async def test_analyze_pillars_fails_safely_on_bad_json():
    agent = CreatorIntelligenceAgent()
    router = _FakeModelRouter("not valid json")
    content = [{"id": "cnt_1", "title": "Post 1", "transcript": "x"}]

    output = await agent._analyze_pillars(content, router)

    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_analyze_pillars_proposes_nothing_when_model_finds_no_pillars():
    """An honest 'no recurring pillars yet' must not turn into an empty
    pillars_upsert change that would still be treated as a successful
    proposal to apply — nothing to sync means no proposed_state_changes."""
    agent = CreatorIntelligenceAgent()
    router = _FakeModelRouter('{"pillars": []}')
    content = [{"id": "cnt_1", "title": "Post 1", "transcript": "x"}]

    output = await agent._analyze_pillars(content, router)

    assert output.status == "success"
    assert output.proposed_state_changes == []


class _ThreeWayRoutingFakeModelRouter:
    """Like _RoutingFakeModelRouter but also distinguishes the pillars
    prompt, so a test can drive all three sub-jobs to different outcomes."""

    def __init__(self, *, positioning_text: str, voice_text: str, pillars_text: str):
        self._positioning_text = positioning_text
        self._voice_text = voice_text
        self._pillars_text = pillars_text

    async def complete(self, *, system, **kwargs):
        if "Infer their voice" in system:
            text = self._voice_text
        elif "recurring content pillars" in system:
            text = self._pillars_text
        else:
            text = self._positioning_text
        return ModelResponse(text=text, model="fake", input_tokens=1, output_tokens=1, latency_ms=1, stub=False)


async def test_run_includes_pillars_when_enough_content(build_snapshot):
    agent = CreatorIntelligenceAgent()
    router = _ThreeWayRoutingFakeModelRouter(
        positioning_text='{"positioning_statement": "x", "expertise": [], "bio": "b"}',
        voice_text='{"tone": "direct", "sentence_style": "short", "pacing": "fast", '
        '"personality": "blunt", "humor_level": "dry", "storytelling_style": "anecdotal", '
        '"opinion_style": "assertive", "signature_phrases": [], "cta_style": "direct ask"}',
        pillars_text='{"pillars": [{"name": "Budgeting", "description": "d", "content_ids": ["cnt_1"]}]}',
    )
    content = [
        {"id": "cnt_1", "title": "Post 1", "transcript": "a"},
        {"id": "cnt_2", "title": "Post 2", "transcript": "b"},
        {"id": "cnt_3", "title": "Post 3", "transcript": "c"},
    ]

    output = await agent.run(build_snapshot(), router, voice_transcripts=content)

    assert output.status == "success"
    change_types = {c["type"] for c in output.proposed_state_changes}
    assert change_types == {"creator_profile_upsert", "voice_profile_upsert", "content_pillars_upsert"}


async def test_run_skips_pillars_below_minimum_content(build_snapshot):
    agent = CreatorIntelligenceAgent()
    router = _RoutingFakeModelRouter(
        positioning_text='{"positioning_statement": "x", "expertise": [], "bio": "b"}',
        voice_text='{"tone": "direct", "sentence_style": "short", "pacing": "fast", '
        '"personality": "blunt", "humor_level": "dry", "storytelling_style": "anecdotal", '
        '"opinion_style": "assertive", "signature_phrases": [], "cta_style": "direct ask"}',
    )
    content = [{"id": "cnt_1", "title": "Post 1", "transcript": "a"}]  # below PILLAR_ANALYSIS_MIN_ITEMS

    output = await agent.run(build_snapshot(), router, voice_transcripts=content)

    change_types = {c["type"] for c in output.proposed_state_changes}
    assert "content_pillars_upsert" not in change_types


class _RateLimitedOnVoiceRouter:
    """Simulates exactly what happened live against Groq's free tier: the
    positioning call succeeds, then the voice call raises a real API-level
    exception (rate limit / network / timeout) rather than returning a
    malformed-but-present response."""

    def __init__(self, positioning_text: str):
        self._positioning_text = positioning_text

    async def complete(self, *, system, **kwargs):
        if "Infer their voice" in system:
            raise RuntimeError("Error code: 429 - Too Many Requests")
        return ModelResponse(
            text=self._positioning_text, model="fake", input_tokens=1, output_tokens=1, latency_ms=1, stub=False
        )


async def test_run_survives_a_subjob_raising_instead_of_returning_bad_json(build_snapshot):
    """Regression test for a real incident: a Groq rate-limit error during
    voice analysis must degrade to a 'failed' voice sub-job while the
    already-succeeded positioning result is still kept (status='partial'),
    not propagate up and discard everything (which is what an uncaught
    exception reaching the Orchestrator's outer handler would do)."""
    agent = CreatorIntelligenceAgent()
    router = _RateLimitedOnVoiceRouter(
        '{"positioning_statement": "x", "expertise": [], "bio": "b"}'
    )
    transcripts = [{"id": "cnt_abc123", "title": "Post 1", "transcript": "some script text"}]

    output = await agent.run(build_snapshot(), router, voice_transcripts=transcripts)

    assert output.status == "partial"
    assert output.proposed_state_changes[0]["type"] == "creator_profile_upsert"
    assert any("429" in w or "Too Many Requests" in w for w in output.warnings)


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
