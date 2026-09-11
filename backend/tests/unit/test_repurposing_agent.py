from datetime import datetime, timezone

import pytest

from app.agent_service.agents.repurposing import RepurposingAgent
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


REPURPOSE_JSON = (
    '{"title": "Budgeting: the envelope method", "body": "1/ Budgeting apps are lying to you...", '
    '"hook_variants": ["a", "b"], "caption_concept": "c", '
    '"transformations": ["condensed 3 examples into 1", "moved mechanism to the hook"]}'
)


async def test_run_parses_live_model_json(build_snapshot):
    agent = RepurposingAgent()
    router = _FakeModelRouter(REPURPOSE_JSON)
    source_item = {"id": "cnt_1", "topic": "budgeting", "platform": "youtube", "format": "long"}

    output = await agent.run(
        build_snapshot(),
        router,
        source_item=source_item,
        source_text="Full script about budgeting with three examples...",
        target_platform="x",
        target_format="thread",
    )

    assert output.status == "success"
    change = output.proposed_state_changes[0]
    assert change["type"] == "repurposed_content_create"
    assert change["data"]["title"] == "Budgeting: the envelope method"
    assert len(change["data"]["transformations"]) == 2


async def test_run_fails_without_source_text(build_snapshot):
    agent = RepurposingAgent()
    output = await agent.run(
        build_snapshot(),
        _FakeModelRouter(REPURPOSE_JSON),
        source_item={"id": "cnt_1", "topic": "budgeting"},
        source_text=None,
        target_platform="x",
        target_format="thread",
    )

    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_run_skips_in_stub_mode_rather_than_guessing(build_snapshot):
    agent = RepurposingAgent()
    output = await agent.run(
        build_snapshot(),
        _StubModelRouter(),
        source_item={"id": "cnt_1", "topic": "budgeting"},
        source_text="Full script...",
        target_platform="x",
        target_format="thread",
    )

    assert output.status == "success"
    assert output.proposed_state_changes == []
    assert any("skipped" in w.lower() for w in output.warnings)


async def test_run_fails_safely_on_bad_json(build_snapshot):
    agent = RepurposingAgent()
    output = await agent.run(
        build_snapshot(),
        _FakeModelRouter("not valid json"),
        source_item={"id": "cnt_1", "topic": "budgeting"},
        source_text="Full script...",
        target_platform="x",
        target_format="thread",
    )

    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_run_survives_model_call_raising(build_snapshot):
    agent = RepurposingAgent()
    output = await agent.run(
        build_snapshot(),
        _RaisingModelRouter(),
        source_item={"id": "cnt_1", "topic": "budgeting"},
        source_text="Full script...",
        target_platform="x",
        target_format="thread",
    )

    assert output.status == "failed"
    assert any("429" in w or "Too Many Requests" in w for w in output.warnings)


async def test_run_includes_source_text_and_target_in_prompt(build_snapshot):
    agent = RepurposingAgent()
    router = _SpyModelRouter(REPURPOSE_JSON)

    await agent.run(
        build_snapshot(),
        router,
        source_item={"id": "cnt_1", "topic": "budgeting"},
        source_text="Full script about the envelope method...",
        target_platform="linkedin",
        target_format="post",
    )

    assert "Full script about the envelope method..." in router.last_kwargs["user"]
    assert "linkedin" in router.last_kwargs["user"]
    assert "post" in router.last_kwargs["user"]
