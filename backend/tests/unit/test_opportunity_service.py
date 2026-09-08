from sqlalchemy import select

from app.domain.content.models import ContentPillar
from app.domain.creator.models import Creator, CreatorPreference, User
from app.domain.research.models import Opportunity, OpportunityEvidence, ResearchSignal
from app.domain.research.service import apply_opportunities, list_opportunities, update_opportunity_status
from app.infrastructure.db.session import AsyncSessionLocal


async def _make_creator() -> str:
    async with AsyncSessionLocal() as session:
        user = User(email="oppservice@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Opp Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def test_apply_opportunities_computes_score_from_components():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await apply_opportunities(
            session,
            creator_id=creator_id,
            opportunities=[
                {
                    "topic": "budgeting",
                    "score_components": {"audience_fit": 0.8, "creator_fit": 0.4},
                    "evidence_signal_ids": [],
                }
            ],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Opportunity).where(Opportunity.creator_id == creator_id))
        opp = result.scalar_one()
    assert opp.score == 0.6
    assert opp.status == "pending"


async def test_apply_opportunities_links_evidence_and_matches_pillar_by_name():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        pillar = ContentPillar(id="pillar_test1", creator_id=creator_id, name="Budgeting", description="d")
        signal = ResearchSignal(id="sig_test1", creator_id=creator_id, topic="budgeting")
        session.add_all([pillar, signal])
        await session.commit()

    async with AsyncSessionLocal() as session:
        await apply_opportunities(
            session,
            creator_id=creator_id,
            opportunities=[
                {
                    "topic": "budgeting",
                    "content_pillar_name": "budgeting",
                    "score_components": {"audience_fit": 0.5},
                    "evidence_signal_ids": ["sig_test1"],
                }
            ],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Opportunity).where(Opportunity.creator_id == creator_id))
        opp = result.scalar_one()
        assert opp.content_pillar_id == "pillar_test1"

        ev_result = await session.execute(
            select(OpportunityEvidence).where(OpportunityEvidence.opportunity_id == opp.id)
        )
        evidence = ev_result.scalars().all()
    assert len(evidence) == 1
    assert evidence[0].research_signal_id == "sig_test1"


async def test_update_status_records_creator_preference_on_reject():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        created = await apply_opportunities(
            session, creator_id=creator_id, opportunities=[{"topic": "budgeting", "evidence_signal_ids": []}]
        )
        await session.commit()
        opportunity_id = created[0].id

    async with AsyncSessionLocal() as session:
        updated = await update_opportunity_status(
            session, creator_id=creator_id, opportunity_id=opportunity_id, status="rejected"
        )
        await session.commit()
    assert updated.status == "rejected"

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CreatorPreference).where(CreatorPreference.creator_id == creator_id)
        )
        prefs = result.scalars().all()
    assert len(prefs) == 1
    assert prefs[0].key == "opportunity_feedback"
    assert prefs[0].value["decision"] == "rejected"
    assert prefs[0].source == "inferred"


async def test_list_opportunities_never_ranks_an_unscored_opportunity_above_a_scored_one():
    """Regression test: Postgres's default DESC ordering puts NULL first, so
    an opportunity with no score_components (score stays NULL) would
    otherwise outrank genuinely scored ones — the opposite of what the
    Opportunities page promises ('ranked, never a single opaque score')."""
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await apply_opportunities(
            session,
            creator_id=creator_id,
            opportunities=[
                {"topic": "unscored", "evidence_signal_ids": []},
                {"topic": "scored", "score_components": {"audience_fit": 0.9}, "evidence_signal_ids": []},
            ],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        opportunities = await list_opportunities(session, creator_id=creator_id)

    assert [o.topic for o in opportunities] == ["scored", "unscored"]


async def test_update_status_returns_none_for_unknown_opportunity():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        result = await update_opportunity_status(
            session, creator_id=creator_id, opportunity_id="opp_missing", status="approved"
        )
    assert result is None
