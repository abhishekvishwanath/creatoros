from datetime import datetime, timezone

import pytest

from app.agent_service.agents.script_agent import ScriptAgent
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
        self.last_system = None

    async def complete(self, *, system, **kwargs):
        self.last_system = system
        return ModelResponse(text=self._text, model="fake", input_tokens=1, output_tokens=1, latency_ms=1, stub=False)


class _RaisingModelRouter:
    async def complete(self, **kwargs):
        raise RuntimeError("boom")


SCRIPT_JSON = '{"body": "hook... body... cta", "hook_variants": ["alt hook 1", "alt hook 2"]}'


async def test_draft_mode_produces_script_create_change(build_snapshot):
    agent = ScriptAgent()
    router = _FakeModelRouter(SCRIPT_JSON)
    brief = {"objective": "o", "angle": "a", "hook": "h", "hook_type": "contrarian", "key_points": ["p1"], "cta": "cta"}

    output = await agent.run(build_snapshot(), router, brief=brief, platform="instagram")

    assert output.status == "success"
    change = output.proposed_state_changes[0]
    assert change["type"] == "script_create"
    assert change["data"]["body"] == "hook... body... cta"
    assert "Infer their voice" not in (router.last_system or "")


async def test_rewrite_mode_uses_rewrite_prompt_and_produces_script_rewrite_change(build_snapshot):
    agent = ScriptAgent()
    router = _FakeModelRouter(SCRIPT_JSON)
    brief = {"objective": "o", "angle": "a", "hook": "h", "hook_type": "contrarian", "key_points": ["p1"], "cta": "cta"}
    issues = [{"type": "weak_hook", "severity": "medium", "location": "opening", "suggestion": "sharpen it"}]

    output = await agent.run(
        build_snapshot(), router, brief=brief, platform="instagram", previous_body="old draft", critic_issues=issues
    )

    assert output.status == "success"
    change = output.proposed_state_changes[0]
    assert change["type"] == "script_rewrite"
    assert "rewriting a script draft" in router.last_system.lower()


async def test_fails_safely_on_bad_json(build_snapshot):
    agent = ScriptAgent()
    router = _FakeModelRouter("not valid json")
    output = await agent.run(build_snapshot(), router, brief={"angle": "a"})

    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_survives_model_call_raising(build_snapshot):
    agent = ScriptAgent()
    output = await agent.run(build_snapshot(), _RaisingModelRouter(), brief={"angle": "a"})

    assert output.status == "failed"
    assert any("boom" in w for w in output.warnings)
