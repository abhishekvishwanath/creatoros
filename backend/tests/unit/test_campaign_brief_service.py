from app.domain.commercial.service import (
    apply_brand_opportunity_score,
    apply_campaign_brief,
    create_brand,
    get_brand_opportunity,
    get_brand_opportunity_by_id,
    get_campaign_brief,
)
from app.domain.creator.models import Creator, User
from app.infrastructure.db.session import AsyncSessionLocal

_creator_counter = 0


async def _make_creator() -> str:
    global _creator_counter
    _creator_counter += 1
    async with AsyncSessionLocal() as session:
        user = User(email=f"cbrief{_creator_counter}@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Campaign Brief Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def _make_scored_opportunity(creator_id: str) -> str:
    async with AsyncSessionLocal() as session:
        brand = await create_brand(session, creator_id=creator_id, data={"name": "Notion"})
        await session.commit()
        brand_id = brand.id

    async with AsyncSessionLocal() as session:
        await apply_brand_opportunity_score(
            session,
            creator_id=creator_id,
            brand_id=brand_id,
            score_components={
                "audience_fit": 0.8,
                "creator_fit": 0.7,
                "product_content_fit": 0.7,
                "timing_signal": 0.5,
                "historical_category_fit": 0.5,
            },
            contactability=0.5,
            reasons="Good overlap",
            evidence_signal_ids=[],
            suggested_contact_roles=[],
            confidence=0.55,
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        opportunity = await get_brand_opportunity(session, brand_id=brand_id)
    return opportunity.id


async def test_apply_campaign_brief_creates_and_reads_back():
    creator_id = await _make_creator()
    opportunity_id = await _make_scored_opportunity(creator_id)

    async with AsyncSessionLocal() as session:
        brief = await apply_campaign_brief(
            session,
            brand_opportunity_id=opportunity_id,
            data={
                "objective_hypothesis": "Grow qualified signups",
                "campaign_concept": "A workflow walkthrough",
                "content_format": "long-form video",
                "why_this_brand": "Matches audience needs",
                "why_now": "No signals given, speculative",
                "suggested_cta": "Try it free",
                "suggested_deliverables": ["1 dedicated video", "2 story mentions"],
                "pitch_angle": "Show, don't tell",
                "personalization_facts": [],
            },
            evidence_signal_ids=[],
            confidence=0.4,
        )
        await session.commit()
        brief_id = brief.id

    assert brief.campaign_concept == "A workflow walkthrough"
    assert brief.suggested_deliverables == ["1 dedicated video", "2 story mentions"]

    async with AsyncSessionLocal() as session:
        reloaded = await get_campaign_brief(session, brand_opportunity_id=opportunity_id)
    assert reloaded.id == brief_id


async def test_apply_campaign_brief_upserts_not_duplicates():
    """Re-generating ("Create pitch" again) must update the existing brief
    in place, mirroring apply_brand_opportunity_score's upsert-by-foreign-key
    discipline — otherwise every re-generation would leave orphaned stale
    rows with no way to tell which one is current."""
    creator_id = await _make_creator()
    opportunity_id = await _make_scored_opportunity(creator_id)

    async with AsyncSessionLocal() as session:
        first = await apply_campaign_brief(
            session,
            brand_opportunity_id=opportunity_id,
            data={"campaign_concept": "first draft"},
            evidence_signal_ids=[],
            confidence=0.3,
        )
        await session.commit()
        first_id = first.id

    async with AsyncSessionLocal() as session:
        second = await apply_campaign_brief(
            session,
            brand_opportunity_id=opportunity_id,
            data={"campaign_concept": "second draft"},
            evidence_signal_ids=[],
            confidence=0.5,
        )
        await session.commit()

    assert second.id == first_id
    assert second.campaign_concept == "second draft"


async def test_get_brand_opportunity_by_id_is_scoped_to_creator():
    creator_a = await _make_creator()
    creator_b = await _make_creator()
    opportunity_id = await _make_scored_opportunity(creator_a)

    async with AsyncSessionLocal() as session:
        found_for_owner = await get_brand_opportunity_by_id(session, creator_id=creator_a, opportunity_id=opportunity_id)
        found_for_other = await get_brand_opportunity_by_id(session, creator_id=creator_b, opportunity_id=opportunity_id)

    assert found_for_owner is not None
    assert found_for_other is None
