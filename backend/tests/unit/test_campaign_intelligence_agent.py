from datetime import datetime, timezone

import pytest

from app.agent_service.agents.campaign_intelligence import CampaignIntelligenceAgent
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


VALID_JSON = (
    '{"objective_hypothesis": "Grow qualified signups", '
    '"campaign_concept": "A workflow walkthrough featuring the tool", '
    '"content_format": "long-form video", '
    '"why_this_brand": "Matches audience needs", '
    '"why_now": "Recently launched a creator program", '
    '"suggested_cta": "Try it free for 30 days", '
    '"suggested_deliverables": ["1 dedicated video", "2 story mentions"], '
    '"pitch_angle": "Show, don\'t tell", '
    '"personalization_facts": ["Launched a creator ambassador program"], '
    '"evidence_signal_ids": ["bsig_1"]}'
)


async def test_run_parses_valid_response_and_grounds_evidence(build_snapshot):
    agent = CampaignIntelligenceAgent()
    router = _FakeModelRouter(VALID_JSON)
    brand = {"id": "brand_1", "name": "Notion", "category": "productivity software"}
    signals = [{"id": "bsig_1", "signal_type": "creator_program", "summary": "Launched an ambassador program"}]
    opportunity = {"id": "bopp_1", "score": 0.7, "score_components": {}, "reasons": "Good overlap"}

    output = await agent.run(build_snapshot(), router, brand=brand, signals=signals, opportunity=opportunity)

    assert output.status == "success"
    change = output.proposed_state_changes[0]
    assert change["type"] == "campaign_brief_upsert"
    assert change["data"]["campaign_concept"] == "A workflow walkthrough featuring the tool"
    assert change["data"]["evidence_signal_ids"] == ["bsig_1"]
    assert change["data"]["suggested_deliverables"] == ["1 dedicated video", "2 story mentions"]
    # Full evidence coverage (the one given signal was cited) -> the
    # _coverage_confidence formula's cap, same as brand_intelligence.py.
    assert output.confidence == 0.6


async def test_run_drops_ungrounded_evidence_ids(build_snapshot):
    """Same hallucination guard as every other grounded agent (CLAUDE.md
    §3.4) — a cited signal id not in the given list must never survive."""
    agent = CampaignIntelligenceAgent()
    json_with_fake_id = VALID_JSON.replace('"bsig_1"', '"bsig_invented"')
    router = _FakeModelRouter(json_with_fake_id)
    brand = {"id": "brand_1", "name": "Notion"}
    signals = [{"id": "bsig_1", "signal_type": "creator_program", "summary": "Launched an ambassador program"}]

    output = await agent.run(build_snapshot(), router, brand=brand, signals=signals)

    change = output.proposed_state_changes[0]
    assert change["data"]["evidence_signal_ids"] == []


async def test_run_caps_deliverables_and_personalization_facts(build_snapshot):
    agent = CampaignIntelligenceAgent()
    many_deliverables = [f"deliverable {i}" for i in range(10)]
    many_facts = [f"fact {i}" for i in range(10)]
    json_with_many = VALID_JSON.replace(
        '"suggested_deliverables": ["1 dedicated video", "2 story mentions"]',
        f'"suggested_deliverables": {many_deliverables}'.replace("'", '"'),
    ).replace(
        '"personalization_facts": ["Launched a creator ambassador program"]',
        f'"personalization_facts": {many_facts}'.replace("'", '"'),
    )
    router = _FakeModelRouter(json_with_many)
    brand = {"id": "brand_1", "name": "Notion"}

    output = await agent.run(build_snapshot(), router, brand=brand, signals=[])

    change = output.proposed_state_changes[0]
    assert len(change["data"]["suggested_deliverables"]) == 5
    assert len(change["data"]["personalization_facts"]) == 4


async def test_run_confidence_is_low_with_no_signals(build_snapshot):
    agent = CampaignIntelligenceAgent()
    json_no_evidence = VALID_JSON.replace('"evidence_signal_ids": ["bsig_1"]', '"evidence_signal_ids": []')
    router = _FakeModelRouter(json_no_evidence)
    brand = {"id": "brand_1", "name": "Notion"}

    output = await agent.run(build_snapshot(), router, brand=brand, signals=[])

    assert output.confidence == 0.3


async def test_run_skips_in_stub_mode(build_snapshot):
    from app.agent_service.model_router.router import ModelResponse as MR

    class _StubRouter:
        async def complete(self, **kwargs):
            return MR(text="", model="stub", input_tokens=0, output_tokens=0, latency_ms=0, stub=True)

    agent = CampaignIntelligenceAgent()
    brand = {"id": "brand_1", "name": "Notion"}

    output = await agent.run(build_snapshot(), _StubRouter(), brand=brand, signals=[])

    assert output.status == "success"
    assert output.proposed_state_changes == []
    assert output.confidence == 0.0
    assert output.warnings


async def test_run_fails_safely_on_bad_json(build_snapshot):
    agent = CampaignIntelligenceAgent()
    router = _FakeModelRouter("not valid json")
    brand = {"id": "brand_1", "name": "Notion"}

    output = await agent.run(build_snapshot(), router, brand=brand, signals=[])

    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_run_survives_model_call_raising(build_snapshot):
    agent = CampaignIntelligenceAgent()
    brand = {"id": "brand_1", "name": "Notion"}

    output = await agent.run(build_snapshot(), _RaisingModelRouter(), brand=brand, signals=[])

    assert output.status == "failed"
