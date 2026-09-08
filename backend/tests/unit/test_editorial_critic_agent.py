from datetime import datetime, timezone

import pytest

from app.agent_service.agents.editorial_critic import EditorialCriticAgent
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


async def test_high_score_no_high_severity_issues_passes(build_snapshot):
    agent = EditorialCriticAgent()
    router = _FakeModelRouter(
        '{"score": 88, "issues": [{"type": "pacing", "severity": "low", "location": "middle", "suggestion": "tighten"}]}'
    )

    output = await agent.run(build_snapshot(), router, script_body="a script", brief={"angle": "a"})

    change = output.proposed_state_changes[0]
    assert change["data"]["passed"] is True


async def test_high_severity_issue_fails_regardless_of_score(build_snapshot):
    """Regression guard: `passed` is computed in code, not trusted from the
    model — a high-severity issue must fail the script even if the model
    gave it a nominally high score."""
    agent = EditorialCriticAgent()
    router = _FakeModelRouter(
        '{"score": 95, "issues": [{"type": "factual_claim", "severity": "high", '
        '"location": "middle", "suggestion": "remove unverifiable stat"}]}'
    )

    output = await agent.run(build_snapshot(), router, script_body="a script", brief={"angle": "a"})

    change = output.proposed_state_changes[0]
    assert change["data"]["passed"] is False


async def test_high_severity_issue_fails_regardless_of_casing(build_snapshot):
    """Regression test: the prompt asks for lowercase severity, but nothing
    enforces that on the model side — 'High'/'HIGH' must still block the
    pass, not silently defeat a case-sensitive gate."""
    agent = EditorialCriticAgent()
    router = _FakeModelRouter(
        '{"score": 95, "issues": [{"type": "factual_claim", "severity": "High", '
        '"location": "middle", "suggestion": "remove unverifiable stat"}]}'
    )

    output = await agent.run(build_snapshot(), router, script_body="a script", brief={"angle": "a"})

    change = output.proposed_state_changes[0]
    assert change["data"]["passed"] is False


async def test_low_score_fails(build_snapshot):
    agent = EditorialCriticAgent()
    router = _FakeModelRouter('{"score": 40, "issues": []}')

    output = await agent.run(build_snapshot(), router, script_body="a script", brief={"angle": "a"})

    change = output.proposed_state_changes[0]
    assert change["data"]["passed"] is False


async def test_fails_safely_on_bad_json(build_snapshot):
    agent = EditorialCriticAgent()
    router = _FakeModelRouter("not valid json")

    output = await agent.run(build_snapshot(), router, script_body="a script", brief={})

    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_survives_model_call_raising(build_snapshot):
    agent = EditorialCriticAgent()
    output = await agent.run(build_snapshot(), _RaisingModelRouter(), script_body="a script", brief={})

    assert output.status == "failed"
