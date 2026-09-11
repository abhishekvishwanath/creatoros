from datetime import datetime, timezone

import pytest

from app.agent_service.agents.experimentation import ExperimentationAgent
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


EVAL_JSON = (
    '{"conclusion": "Contrarian hooks appear to modestly improve retention.", '
    '"confidence": "medium", "next_action": "Test on more posts.", "retain_hypothesis": true}'
)

ADEQUATE_STATS = {
    "retention": {
        "test_n": 3, "control_n": 3, "test_median": 42.0, "control_median": 31.0,
        "delta": 11.0, "pct_delta": 0.35, "adequate_evidence": True,
    }
}

THIN_STATS = {
    "retention": {
        "test_n": 1, "control_n": 1, "test_median": 42.0, "control_median": 31.0,
        "delta": 11.0, "pct_delta": 0.35, "adequate_evidence": False,
    }
}


async def test_run_skips_when_no_metric_has_adequate_evidence(build_snapshot):
    agent = ExperimentationAgent()
    output = await agent.run(
        build_snapshot(), _FakeModelRouter(EVAL_JSON), hypothesis="h", stats=THIN_STATS
    )
    assert output.status == "success"
    assert output.proposed_state_changes == []
    assert any("2 results" in w for w in output.warnings)


async def test_run_parses_live_model_json(build_snapshot):
    agent = ExperimentationAgent()
    output = await agent.run(
        build_snapshot(), _FakeModelRouter(EVAL_JSON), hypothesis="Contrarian hooks help.", variable="hook_type",
        stats=ADEQUATE_STATS,
    )
    assert output.status == "success"
    change = output.proposed_state_changes[0]
    assert change["type"] == "experiment_evaluation"
    assert change["data"]["retain_hypothesis"] is True


async def test_run_skips_in_stub_mode_rather_than_guessing(build_snapshot):
    agent = ExperimentationAgent()
    output = await agent.run(build_snapshot(), _StubModelRouter(), hypothesis="h", stats=ADEQUATE_STATS)
    assert output.status == "success"
    assert output.proposed_state_changes == []
    assert any("skipped" in w.lower() for w in output.warnings)


async def test_run_fails_safely_on_bad_json(build_snapshot):
    agent = ExperimentationAgent()
    output = await agent.run(build_snapshot(), _FakeModelRouter("not valid json"), hypothesis="h", stats=ADEQUATE_STATS)
    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_run_survives_model_call_raising(build_snapshot):
    agent = ExperimentationAgent()
    output = await agent.run(build_snapshot(), _RaisingModelRouter(), hypothesis="h", stats=ADEQUATE_STATS)
    assert output.status == "failed"
    assert any("429" in w or "Too Many Requests" in w for w in output.warnings)


async def test_run_includes_stats_in_prompt(build_snapshot):
    agent = ExperimentationAgent()
    router = _SpyModelRouter(EVAL_JSON)
    await agent.run(build_snapshot(), router, hypothesis="Contrarian hooks help.", stats=ADEQUATE_STATS)
    assert "retention" in router.last_kwargs["user"]
    assert "42.0" in router.last_kwargs["user"]
