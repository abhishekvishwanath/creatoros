from datetime import datetime, timezone

import pytest

from app.agent_service.agents.outreach import OutreachAgent
from app.agent_service.model_router.router import ModelResponse
from app.schemas.creator import CreatorRead, CreatorStateSnapshot


@pytest.fixture
def build_snapshot():
    def _build(**overrides) -> CreatorStateSnapshot:
        now = datetime.now(timezone.utc)
        creator = CreatorRead(
            id="cr_test", name="Test Creator", niche="cooking", onboarding_status="created", created_at=now, updated_at=now
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


VALID_JSON = '{"subject": "Loved your ambassador program", "body": "Hi there, I would love to explore something together."}'


async def test_run_drafts_initial_pitch(build_snapshot):
    agent = OutreachAgent()
    router = _FakeModelRouter(VALID_JSON)
    brand = {"name": "Notion", "category": "productivity"}
    brief = {"pitch_angle": "Show, don't tell", "suggested_cta": "Try it free"}

    output = await agent.run(build_snapshot(), router, brand=brand, brief=brief, kind="initial_pitch")

    assert output.status == "success"
    change = output.proposed_state_changes[0]
    assert change["type"] == "outreach_message_draft"
    assert change["data"]["subject"] == "Loved your ambassador program"
    assert "explore something together" in change["data"]["body"]


async def test_run_drafts_follow_up_with_prior_messages(build_snapshot):
    agent = OutreachAgent()
    router = _FakeModelRouter(VALID_JSON)
    brand = {"name": "Notion"}
    brief = {"pitch_angle": "Show, don't tell"}
    prior = [{"direction": "outbound", "kind": "initial_pitch", "body": "Hi there, initial pitch text."}]

    output = await agent.run(build_snapshot(), router, brand=brand, brief=brief, kind="follow_up", prior_messages=prior)

    assert output.status == "success"
    assert output.proposed_state_changes[0]["data"]["body"]


async def test_run_skips_in_stub_mode(build_snapshot):
    class _StubRouter:
        async def complete(self, **kwargs):
            return ModelResponse(text="", model="stub", input_tokens=0, output_tokens=0, latency_ms=0, stub=True)

    agent = OutreachAgent()
    output = await agent.run(build_snapshot(), _StubRouter(), brand={"name": "Notion"}, brief={})

    assert output.status == "success"
    assert output.proposed_state_changes == []
    assert output.confidence == 0.0
    assert output.warnings


async def test_run_fails_on_empty_body(build_snapshot):
    agent = OutreachAgent()
    router = _FakeModelRouter('{"subject": "Hi", "body": "   "}')

    output = await agent.run(build_snapshot(), router, brand={"name": "Notion"}, brief={})

    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_run_fails_safely_on_bad_json(build_snapshot):
    agent = OutreachAgent()
    router = _FakeModelRouter("not valid json")

    output = await agent.run(build_snapshot(), router, brand={"name": "Notion"}, brief={})

    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_run_survives_model_call_raising(build_snapshot):
    agent = OutreachAgent()

    output = await agent.run(build_snapshot(), _RaisingModelRouter(), brand={"name": "Notion"}, brief={})

    assert output.status == "failed"


async def test_run_never_proposes_status_or_decision_fields(build_snapshot):
    """CLAUDE.md §66 hard constraint: the agent's output can only ever be a
    message draft — it must have no mechanism to propose a thread status,
    outcome, or creator_decision change, even indirectly via extra JSON
    keys the model might hallucinate."""
    agent = OutreachAgent()
    router = _FakeModelRouter(
        '{"subject": "Hi", "body": "Let\'s do this deal!", "status": "sent", "creator_decision": "accepted"}'
    )

    output = await agent.run(build_snapshot(), router, brand={"name": "Notion"}, brief={})

    change = output.proposed_state_changes[0]
    assert set(change["data"].keys()) == {"subject", "body"}
