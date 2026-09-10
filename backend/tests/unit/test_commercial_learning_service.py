from app.domain.commercial.service import (
    add_outreach_message,
    apply_brand_opportunity_score,
    approve_outreach_message,
    create_brand,
    create_outreach_thread,
    get_brand_opportunity,
    mark_outreach_message_sent,
    record_creator_decision,
)
from app.domain.creator.models import Creator, User
from app.domain.experiments.service import (
    MIN_LEARNING_EVIDENCE,
    collect_commercial_learning_candidates,
    sync_commercial_learnings,
)
from app.infrastructure.db.session import AsyncSessionLocal

_creator_counter = 0


async def _make_creator() -> str:
    global _creator_counter
    _creator_counter += 1
    async with AsyncSessionLocal() as session:
        user = User(email=f"clearn{_creator_counter}@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Commercial Learning Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def _make_resolved_thread(creator_id: str, *, brand_name: str, category: str, decision: str) -> str:
    """A brand, scored, with a sent-and-decided outreach thread — the
    minimum state collect_commercial_learning_candidates reads from."""
    async with AsyncSessionLocal() as session:
        brand = await create_brand(session, creator_id=creator_id, data={"name": brand_name, "category": category})
        await session.commit()
        brand_id = brand.id

    async with AsyncSessionLocal() as session:
        await apply_brand_opportunity_score(
            session,
            creator_id=creator_id,
            brand_id=brand_id,
            score_components={
                "audience_fit": 0.5,
                "creator_fit": 0.5,
                "product_content_fit": 0.5,
                "timing_signal": 0.5,
                "historical_category_fit": 0.5,
            },
            contactability=0.5,
            reasons="",
            evidence_signal_ids=[],
            suggested_contact_roles=[],
            confidence=0.5,
        )
        await session.commit()
        opportunity = await get_brand_opportunity(session, brand_id=brand_id)
        opportunity_id = opportunity.id

    async with AsyncSessionLocal() as session:
        thread = await create_outreach_thread(session, creator_id=creator_id, brand_opportunity_id=opportunity_id)
        message = await add_outreach_message(
            session, thread_id=thread.id, direction="outbound", kind="initial_pitch", subject="s", body="b", status="draft"
        )
        await session.commit()
        thread_id, message_id = thread.id, message.id

    async with AsyncSessionLocal() as session:
        await approve_outreach_message(session, message_id=message_id)
        await mark_outreach_message_sent(session, message_id=message_id)
        await session.commit()

    async with AsyncSessionLocal() as session:
        await record_creator_decision(session, thread_id=thread_id, decision=decision)
        await session.commit()

    return thread_id


async def test_collect_commercial_candidates_requires_min_evidence():
    creator_id = await _make_creator()
    assert MIN_LEARNING_EVIDENCE == 2  # test assumes this; keep in sync if the constant changes
    await _make_resolved_thread(creator_id, brand_name="Brand A", category="AI tools", decision="accept")

    async with AsyncSessionLocal() as session:
        candidates = await collect_commercial_learning_candidates(session, creator_id=creator_id)
    assert candidates == []  # only one accepted deal — below the evidence threshold


async def test_collect_commercial_candidates_clusters_by_category_and_direction():
    creator_id = await _make_creator()
    await _make_resolved_thread(creator_id, brand_name="Brand A", category="AI tools", decision="accept")
    await _make_resolved_thread(creator_id, brand_name="Brand B", category="AI tools", decision="accept")

    async with AsyncSessionLocal() as session:
        candidates = await collect_commercial_learning_candidates(session, creator_id=creator_id)

    assert len(candidates) == 1
    assert candidates[0]["direction"] == "positive"
    assert candidates[0]["label"] == "AI tools"
    assert len(candidates[0]["evidence_ids"]) == 2


async def test_collect_commercial_candidates_ignores_archived_outcome():
    """'archive' has no clear directional signal (could mean many things)
    — CLAUDE.md §29: don't overclaim from an ambiguous signal."""
    creator_id = await _make_creator()
    await _make_resolved_thread(creator_id, brand_name="Brand A", category="Alcohol", decision="archive")
    await _make_resolved_thread(creator_id, brand_name="Brand B", category="Alcohol", decision="archive")

    async with AsyncSessionLocal() as session:
        candidates = await collect_commercial_learning_candidates(session, creator_id=creator_id)
    assert candidates == []


async def test_collect_commercial_candidates_separates_positive_and_negative():
    creator_id = await _make_creator()
    await _make_resolved_thread(creator_id, brand_name="Brand A", category="Fitness gear", decision="accept")
    await _make_resolved_thread(creator_id, brand_name="Brand B", category="Fitness gear", decision="accept")
    await _make_resolved_thread(creator_id, brand_name="Brand C", category="Fitness gear", decision="decline")
    await _make_resolved_thread(creator_id, brand_name="Brand D", category="Fitness gear", decision="decline")

    async with AsyncSessionLocal() as session:
        candidates = await collect_commercial_learning_candidates(session, creator_id=creator_id)

    directions = sorted(c["direction"] for c in candidates)
    assert directions == ["negative", "positive"]


async def test_sync_commercial_learnings_creates_category_prefixed_row():
    creator_id = await _make_creator()
    await _make_resolved_thread(creator_id, brand_name="Brand A", category="Productivity tools", decision="accept")
    await _make_resolved_thread(creator_id, brand_name="Brand B", category="Productivity tools", decision="accept")

    async with AsyncSessionLocal() as session:
        learnings = await sync_commercial_learnings(session, creator_id=creator_id)
        await session.commit()

    assert len(learnings) == 1
    learning = learnings[0]
    assert learning.category.startswith("commercial/positive/")
    assert "productivity_tools" in learning.category
    assert len(learning.evidence_ids) == 2
    assert learning.status == "active"


async def test_sync_commercial_learnings_is_idempotent_and_upserts():
    creator_id = await _make_creator()
    await _make_resolved_thread(creator_id, brand_name="Brand A", category="Skincare", decision="decline")
    await _make_resolved_thread(creator_id, brand_name="Brand B", category="Skincare", decision="decline")

    async with AsyncSessionLocal() as session:
        first = await sync_commercial_learnings(session, creator_id=creator_id)
        await session.commit()
        first_id = first[0].id

    await _make_resolved_thread(creator_id, brand_name="Brand C", category="Skincare", decision="decline")

    async with AsyncSessionLocal() as session:
        second = await sync_commercial_learnings(session, creator_id=creator_id)
        await session.commit()

    assert len(second) == 1
    assert second[0].id == first_id  # same row, updated in place
    assert len(second[0].evidence_ids) == 3


async def test_sync_commercial_learnings_never_resurrects_a_retracted_learning():
    """CLAUDE.md §3.2: the creator's override always wins over a re-sync."""
    from app.domain.experiments.service import set_learning_status

    creator_id = await _make_creator()
    await _make_resolved_thread(creator_id, brand_name="Brand A", category="Gambling", decision="accept")
    await _make_resolved_thread(creator_id, brand_name="Brand B", category="Gambling", decision="accept")

    async with AsyncSessionLocal() as session:
        learnings = await sync_commercial_learnings(session, creator_id=creator_id)
        await session.commit()
        learning_id = learnings[0].id

    async with AsyncSessionLocal() as session:
        await set_learning_status(session, creator_id=creator_id, learning_id=learning_id, status="retracted")
        await session.commit()

    await _make_resolved_thread(creator_id, brand_name="Brand C", category="Gambling", decision="accept")

    async with AsyncSessionLocal() as session:
        touched = await sync_commercial_learnings(session, creator_id=creator_id)
        await session.commit()

    assert touched == []  # the retracted row was not touched/resurrected
