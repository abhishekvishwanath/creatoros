from app.domain.commercial.service import (
    apply_brand_opportunity_score,
    create_brand,
    get_brand_opportunity,
    list_brand_opportunities,
)
from app.domain.creator.models import Creator, User
from app.infrastructure.db.session import AsyncSessionLocal

_creator_counter = 0


async def _make_creator() -> str:
    global _creator_counter
    _creator_counter += 1
    async with AsyncSessionLocal() as session:
        user = User(email=f"bopp{_creator_counter}@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Brand Opp Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def test_apply_score_computes_combined_score_including_contactability():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        brand = await create_brand(session, creator_id=creator_id, data={"name": "Notion"})
        await session.commit()
        brand_id = brand.id

    async with AsyncSessionLocal() as session:
        opportunity = await apply_brand_opportunity_score(
            session,
            creator_id=creator_id,
            brand_id=brand_id,
            score_components={
                "audience_fit": 0.8,
                "creator_fit": 0.6,
                "product_content_fit": 0.7,
                "timing_signal": 0.5,
                "historical_category_fit": 0.5,
            },
            contactability=1.0,
            reasons="Good fit",
            evidence_signal_ids=["bsig_1"],
            suggested_contact_roles=["Creator Partnerships Manager"],
            confidence=0.55,
        )
        await session.commit()

    # mean(0.8, 0.6, 0.7, 0.5, 0.5, 1.0) = 4.1 / 6 = 0.6833...
    assert opportunity.score == round((0.8 + 0.6 + 0.7 + 0.5 + 0.5 + 1.0) / 6, 3)
    assert opportunity.score_components["contactability"] == 1.0


async def test_apply_score_upserts_by_brand_not_duplicates():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        brand = await create_brand(session, creator_id=creator_id, data={"name": "Notion"})
        await session.commit()
        brand_id = brand.id

    async with AsyncSessionLocal() as session:
        first = await apply_brand_opportunity_score(
            session,
            creator_id=creator_id,
            brand_id=brand_id,
            score_components={"audience_fit": 0.5, "creator_fit": 0.5, "product_content_fit": 0.5, "timing_signal": 0.5, "historical_category_fit": 0.5},
            contactability=0.0,
            reasons="first",
            evidence_signal_ids=[],
            suggested_contact_roles=[],
            confidence=0.3,
        )
        await session.commit()
        first_id = first.id

    async with AsyncSessionLocal() as session:
        second = await apply_brand_opportunity_score(
            session,
            creator_id=creator_id,
            brand_id=brand_id,
            score_components={"audience_fit": 0.9, "creator_fit": 0.9, "product_content_fit": 0.9, "timing_signal": 0.9, "historical_category_fit": 0.9},
            contactability=1.0,
            reasons="second",
            evidence_signal_ids=[],
            suggested_contact_roles=[],
            confidence=0.8,
        )
        await session.commit()

    assert second.id == first_id
    assert second.reasons == "second"

    async with AsyncSessionLocal() as session:
        opportunity = await get_brand_opportunity(session, brand_id=brand_id)
    assert opportunity.reasons == "second"


async def test_list_brand_opportunities_ranked_by_score_desc():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        brand_low = await create_brand(session, creator_id=creator_id, data={"name": "Low Fit Co"})
        brand_high = await create_brand(session, creator_id=creator_id, data={"name": "High Fit Co"})
        await session.commit()
        low_id, high_id = brand_low.id, brand_high.id

    async with AsyncSessionLocal() as session:
        await apply_brand_opportunity_score(
            session, creator_id=creator_id, brand_id=low_id,
            score_components={"audience_fit": 0.2, "creator_fit": 0.2, "product_content_fit": 0.2, "timing_signal": 0.2, "historical_category_fit": 0.2},
            contactability=0.0, reasons="", evidence_signal_ids=[], suggested_contact_roles=[], confidence=0.3,
        )
        await apply_brand_opportunity_score(
            session, creator_id=creator_id, brand_id=high_id,
            score_components={"audience_fit": 0.9, "creator_fit": 0.9, "product_content_fit": 0.9, "timing_signal": 0.9, "historical_category_fit": 0.9},
            contactability=1.0, reasons="", evidence_signal_ids=[], suggested_contact_roles=[], confidence=0.8,
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        rows = await list_brand_opportunities(session, creator_id=creator_id)
    names_in_order = [brand.name for _, brand in rows]
    assert names_in_order == ["High Fit Co", "Low Fit Co"]


async def test_score_with_missing_dimensions_uses_fixed_denominator():
    """Regression: a brand scored on only 3 of 5 dimensions (the other 2
    dropped upstream by the agent's grounding checks) must not be able to
    out-rank a brand honestly scored on all 5 just by having a smaller,
    easier-to-satisfy denominator. Missing dimensions count as neutral 0.5
    in the score math, but are NOT added to the persisted/displayed
    score_components (that stays only what was actually grounded)."""
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        brand = await create_brand(session, creator_id=creator_id, data={"name": "Partial Co"})
        await session.commit()
        brand_id = brand.id

    async with AsyncSessionLocal() as session:
        opportunity = await apply_brand_opportunity_score(
            session,
            creator_id=creator_id,
            brand_id=brand_id,
            # Only 3 of the 5 canonical dimensions given — as if the other 2
            # were dropped by the agent's out-of-range/missing validation.
            score_components={"audience_fit": 0.9, "creator_fit": 0.9, "product_content_fit": 0.9},
            contactability=1.0,
            reasons="partial",
            evidence_signal_ids=[],
            suggested_contact_roles=[],
            confidence=0.5,
        )
        await session.commit()

    # (0.9 + 0.9 + 0.9 + 0.5[timing_signal] + 0.5[historical_category_fit] + 1.0[contactability]) / 6
    expected = round((0.9 + 0.9 + 0.9 + 0.5 + 0.5 + 1.0) / 6, 3)
    assert opportunity.score == expected
    # Displayed components keep only what was actually grounded (plus the
    # always-code-computed contactability) — the neutral fill-ins used for
    # score math are never presented as if the model scored them.
    assert set(opportunity.score_components.keys()) == {"audience_fit", "creator_fit", "product_content_fit", "contactability"}


async def test_score_persists_prohibited_conflict_flag():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        brand = await create_brand(session, creator_id=creator_id, data={"name": "Conflict Co", "category": "alcohol"})
        await session.commit()
        brand_id = brand.id

    async with AsyncSessionLocal() as session:
        opportunity = await apply_brand_opportunity_score(
            session,
            creator_id=creator_id,
            brand_id=brand_id,
            score_components={"audience_fit": 0.5, "creator_fit": 0.5, "product_content_fit": 0.5, "timing_signal": 0.5, "historical_category_fit": 0.5},
            contactability=0.0,
            reasons="conflicts with prohibited category",
            evidence_signal_ids=[],
            suggested_contact_roles=[],
            confidence=0.3,
            prohibited_conflict=True,
        )
        await session.commit()

    assert opportunity.prohibited_conflict is True

    async with AsyncSessionLocal() as session:
        reloaded = await get_brand_opportunity(session, brand_id=brand_id)
    assert reloaded.prohibited_conflict is True


async def test_concurrent_score_for_same_brand_is_rejected_at_db_level():
    """Regression guard: the unique constraint on brand_id is the backstop
    against a race between two concurrent inserts for the same brand (same
    bug class as CalendarEvent's content_item_id constraint from an earlier
    phase, and StrategicLearning's (creator_id, category) constraint) — the
    ORM-level select-then-insert in apply_brand_opportunity_score has a
    window where two concurrent callers could both see no row and both
    attempt an insert; the DB constraint is what actually prevents a
    duplicate row, surfacing as IntegrityError rather than silent
    duplication."""
    from sqlalchemy.exc import IntegrityError

    from app.core.ids import generate_id
    from app.domain.commercial.models import BrandOpportunity

    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        brand = await create_brand(session, creator_id=creator_id, data={"name": "Race Co"})
        await session.commit()
        brand_id = brand.id

    async with AsyncSessionLocal() as session:
        session.add(BrandOpportunity(id=generate_id("brand_opportunity"), creator_id=creator_id, brand_id=brand_id))
        await session.commit()

    async with AsyncSessionLocal() as session:
        session.add(BrandOpportunity(id=generate_id("brand_opportunity"), creator_id=creator_id, brand_id=brand_id))
        try:
            await session.commit()
            assert False, "expected IntegrityError"
        except IntegrityError:
            await session.rollback()
