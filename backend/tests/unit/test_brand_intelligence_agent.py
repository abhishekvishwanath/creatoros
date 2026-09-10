from datetime import datetime, timezone

import pytest

from app.agent_service.agents.brand_intelligence import BrandIntelligenceAgent
from app.agent_service.model_router.router import ModelResponse
from app.schemas.commercial import CommercialProfileRead
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
    '{"score_components": {"audience_fit": 0.8, "creator_fit": 0.7, "product_content_fit": 0.75, '
    '"timing_signal": 0.6, "historical_category_fit": 0.5}, '
    '"reasons": "Strong overlap between this brand and the creator\'s audience.", '
    '"evidence_signal_ids": ["bsig_1"], "contact_roles": ["Creator Partnerships Manager"], "confidence": "medium"}'
)


async def test_run_parses_valid_response_and_grounds_evidence(build_snapshot):
    agent = BrandIntelligenceAgent()
    router = _FakeModelRouter(VALID_JSON)
    brand = {"id": "brand_1", "name": "Notion", "category": "productivity software"}
    signals = [{"id": "bsig_1", "signal_type": "creator_program", "summary": "Launched an ambassador program"}]

    output = await agent.run(build_snapshot(), router, brand=brand, signals=signals, contactability=0.5)

    assert output.status == "success"
    change = output.proposed_state_changes[0]
    assert change["type"] == "brand_opportunity_score"
    assert change["data"]["score_components"]["audience_fit"] == 0.8
    assert change["data"]["evidence_signal_ids"] == ["bsig_1"]
    assert change["data"]["suggested_contact_roles"] == ["Creator Partnerships Manager"]
    assert change["data"]["prohibited_conflict"] is False
    # Confidence is evidence-coverage based (BaseAgent._coverage_confidence),
    # not the model's self-reported "medium" string in VALID_JSON — the one
    # given signal was fully cited, so coverage=1.0 -> the formula's cap.
    assert output.confidence == 0.6


async def test_run_confidence_is_low_with_no_signals_regardless_of_self_report(build_snapshot):
    """A brand with zero observed signals must not be able to reach a high
    confidence just because the model's own JSON says "confidence": "high" —
    confidence is earned by grounded evidence coverage, not asserted."""
    agent = BrandIntelligenceAgent()
    json_claiming_high = VALID_JSON.replace('"confidence": "medium"', '"confidence": "high"').replace(
        '"evidence_signal_ids": ["bsig_1"]', '"evidence_signal_ids": []'
    )
    router = _FakeModelRouter(json_claiming_high)
    brand = {"id": "brand_1", "name": "Notion", "category": "productivity software"}

    output = await agent.run(build_snapshot(), router, brand=brand, signals=[])

    assert output.confidence == 0.3


async def test_run_drops_ungrounded_evidence_ids(build_snapshot):
    """A cited signal id not in the given list must never survive — same
    hallucination guard as the Opportunity Engine (CLAUDE.md §3.4)."""
    agent = BrandIntelligenceAgent()
    json_with_fake_id = VALID_JSON.replace('"bsig_1"', '"bsig_invented"')
    router = _FakeModelRouter(json_with_fake_id)
    brand = {"id": "brand_1", "name": "Notion", "category": "productivity software"}
    signals = [{"id": "bsig_1", "signal_type": "creator_program", "summary": "Launched an ambassador program"}]

    output = await agent.run(build_snapshot(), router, brand=brand, signals=signals)

    change = output.proposed_state_changes[0]
    assert change["data"]["evidence_signal_ids"] == []


async def test_run_drops_out_of_range_score_components(build_snapshot):
    agent = BrandIntelligenceAgent()
    bad_json = VALID_JSON.replace('"audience_fit": 0.8', '"audience_fit": 1.8')
    router = _FakeModelRouter(bad_json)
    brand = {"id": "brand_1", "name": "Notion", "category": "productivity software"}

    output = await agent.run(build_snapshot(), router, brand=brand, signals=[])

    change = output.proposed_state_changes[0]
    assert "audience_fit" not in change["data"]["score_components"]
    assert "creator_fit" in change["data"]["score_components"]


async def test_run_fails_when_no_components_survive_grounding(build_snapshot):
    agent = BrandIntelligenceAgent()
    router = _FakeModelRouter('{"score_components": {}, "reasons": "x", "evidence_signal_ids": [], "confidence": "low"}')
    brand = {"id": "brand_1", "name": "Notion"}

    output = await agent.run(build_snapshot(), router, brand=brand, signals=[])

    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_run_flags_prohibited_category_conflict(build_snapshot):
    agent = BrandIntelligenceAgent()
    router = _FakeModelRouter(VALID_JSON)
    brand = {"id": "brand_1", "name": "Boozy Co", "category": "alcohol"}
    snapshot = build_snapshot(
        commercial_profile=CommercialProfileRead(
            id="cmprof_1", version=1, prohibited_categories=["alcohol"], confidence=1.0
        )
    )

    output = await agent.run(snapshot, router, brand=brand, signals=[])

    change = output.proposed_state_changes[0]
    assert change["data"]["prohibited_conflict"] is True
    assert any("prohibited" in w.lower() for w in output.warnings)


async def test_run_fails_safely_on_bad_json(build_snapshot):
    agent = BrandIntelligenceAgent()
    router = _FakeModelRouter("not valid json")
    brand = {"id": "brand_1", "name": "Notion"}

    output = await agent.run(build_snapshot(), router, brand=brand, signals=[])

    assert output.status == "failed"
    assert output.proposed_state_changes == []


async def test_run_survives_model_call_raising(build_snapshot):
    agent = BrandIntelligenceAgent()
    brand = {"id": "brand_1", "name": "Notion"}

    output = await agent.run(build_snapshot(), _RaisingModelRouter(), brand=brand, signals=[])

    assert output.status == "failed"
