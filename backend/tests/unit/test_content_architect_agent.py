from datetime import datetime, timezone

import pytest

from app.agent_service.agents.content_architect import ContentArchitectAgent
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


class _SpyModelRouter:
    def __init__(self, text: str):
        self._text = text
        self.last_kwargs: dict = {}

    async def complete(self, **kwargs):
        self.last_kwargs = kwargs
        return ModelResponse(text=self._text, model="fake", input_tokens=1, output_tokens=1, latency_ms=1, stub=False)


BRIEF_JSON = (
    '{"objective": "Teach budgeting basics", "core_insight": "x", "angle": "envelope method", '
    '"hook_type": "contrarian", "hook": "Budgeting apps are lying to you", '
    '"narrative_structure": {"hook": "...", "body": "..."}, "key_points": ["a", "b"], '
    '"examples": [], "broll_suggestions": [], "on_screen_text": [], "pacing": "fast", '
    '"cta": "Try it this week", "caption_concept": "c", "cover_concept": "d", '
    '"repurposing_opportunities": [], "risk_notes": "", "evidence_signal_ids": ["sig_1"]}'
)


async def test_run_parses_live_model_json_and_grounds_evidence(build_snapshot):
    agent = ContentArchitectAgent()
    router = _FakeModelRouter(BRIEF_JSON)
    content_item = {"id": "cnt_1", "topic": "budgeting", "format": "short", "title": "budgeting"}
    evidence_signals = [{"id": "sig_1", "topic": "budgeting", "summary": "x"}]

    output = await agent.run(build_snapshot(), router, content_item=content_item, evidence_signals=evidence_signals)

    assert output.status == "success"
    change = output.proposed_state_changes[0]
    assert change["type"] == "content_brief_upsert"
    assert change["data"]["angle"] == "envelope method"
    assert output.evidence_ids == ["sig_1"]


async def test_run_drops_hallucinated_evidence_ids(build_snapshot):
    agent = ContentArchitectAgent()
    router = _FakeModelRouter(BRIEF_JSON)
    content_item = {"id": "cnt_1", "topic": "budgeting", "format": "short", "title": "budgeting"}
    # No evidence_signals given, so "sig_1" cited by the model is ungrounded.
    output = await agent.run(build_snapshot(), router, content_item=content_item, evidence_signals=[])

    assert output.evidence_ids == []


async def test_run_fails_safely_on_bad_json(build_snapshot):
    agent = ContentArchitectAgent()
    router = _FakeModelRouter("not valid json")
    content_item = {"id": "cnt_1", "topic": "budgeting", "format": "short", "title": "budgeting"}

    output = await agent.run(build_snapshot(), router, content_item=content_item)

    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_run_survives_model_call_raising(build_snapshot):
    agent = ContentArchitectAgent()
    content_item = {"id": "cnt_1", "topic": "budgeting", "format": "short", "title": "budgeting"}

    output = await agent.run(build_snapshot(), _RaisingModelRouter(), content_item=content_item)

    assert output.status == "failed"
    assert any("429" in w or "Too Many Requests" in w for w in output.warnings)


async def test_run_includes_strategic_learnings_in_the_prompt(build_snapshot):
    agent = ContentArchitectAgent()
    router = _SpyModelRouter(BRIEF_JSON)
    content_item = {"id": "cnt_1", "topic": "budgeting", "format": "short", "title": "budgeting"}
    snapshot = build_snapshot(
        strategic_learnings=[{"id": "sl_1", "statement": "Contrarian hooks outperform.", "scope": "creator-wide", "confidence": 0.6}]
    )

    await agent.run(snapshot, router, content_item=content_item)

    assert "Contrarian hooks outperform." in router.last_kwargs["user"]
