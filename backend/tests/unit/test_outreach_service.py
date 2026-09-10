import pytest

from app.domain.commercial.service import (
    add_outreach_message,
    apply_brand_opportunity_score,
    apply_campaign_brief,
    approve_outreach_message,
    create_brand,
    create_outreach_thread,
    get_brand_opportunity,
    get_outreach_message,
    get_outreach_thread,
    list_outreach_messages,
    list_outreach_threads,
    mark_outreach_message_sent,
)
from app.domain.creator.models import Creator, User
from app.infrastructure.db.session import AsyncSessionLocal

_creator_counter = 0


async def _make_creator() -> str:
    global _creator_counter
    _creator_counter += 1
    async with AsyncSessionLocal() as session:
        user = User(email=f"othread{_creator_counter}@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Outreach Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def _make_scored_opportunity(creator_id: str, brand_name: str = "Notion") -> str:
    async with AsyncSessionLocal() as session:
        brand = await create_brand(session, creator_id=creator_id, data={"name": brand_name})
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


async def test_create_thread_and_add_message_round_trip():
    creator_id = await _make_creator()
    opportunity_id = await _make_scored_opportunity(creator_id)

    async with AsyncSessionLocal() as session:
        thread = await create_outreach_thread(session, creator_id=creator_id, brand_opportunity_id=opportunity_id)
        await session.commit()
        thread_id = thread.id

    assert thread.status == "drafting"

    async with AsyncSessionLocal() as session:
        message = await add_outreach_message(
            session,
            thread_id=thread_id,
            direction="outbound",
            kind="initial_pitch",
            subject="Let's work together",
            body="Hi there, ...",
            status="draft",
        )
        await session.commit()
        message_id = message.id

    assert message.status == "draft"

    async with AsyncSessionLocal() as session:
        messages = await list_outreach_messages(session, thread_id=thread_id)
    assert [m.id for m in messages] == [message_id]


async def test_thread_lookup_is_scoped_to_owning_creator():
    creator_a = await _make_creator()
    creator_b = await _make_creator()
    opportunity_id = await _make_scored_opportunity(creator_a)

    async with AsyncSessionLocal() as session:
        thread = await create_outreach_thread(session, creator_id=creator_a, brand_opportunity_id=opportunity_id)
        await session.commit()
        thread_id = thread.id

    async with AsyncSessionLocal() as session:
        found_for_owner = await get_outreach_thread(session, creator_id=creator_a, thread_id=thread_id)
        found_for_other = await get_outreach_thread(session, creator_id=creator_b, thread_id=thread_id)

    assert found_for_owner is not None
    assert found_for_other is None


async def test_list_outreach_threads_joins_brand_and_orders_newest_first():
    creator_id = await _make_creator()
    opp_1 = await _make_scored_opportunity(creator_id, brand_name="First Co")
    opp_2 = await _make_scored_opportunity(creator_id, brand_name="Second Co")

    async with AsyncSessionLocal() as session:
        await create_outreach_thread(session, creator_id=creator_id, brand_opportunity_id=opp_1)
        await session.commit()
        await create_outreach_thread(session, creator_id=creator_id, brand_opportunity_id=opp_2)
        await session.commit()

    async with AsyncSessionLocal() as session:
        rows = await list_outreach_threads(session, creator_id=creator_id)

    names = [brand.name for _, brand in rows]
    assert names == ["Second Co", "First Co"]


async def test_approve_message_advances_thread_and_message_status():
    creator_id = await _make_creator()
    opportunity_id = await _make_scored_opportunity(creator_id)

    async with AsyncSessionLocal() as session:
        thread = await create_outreach_thread(session, creator_id=creator_id, brand_opportunity_id=opportunity_id)
        message = await add_outreach_message(
            session, thread_id=thread.id, direction="outbound", kind="initial_pitch", subject="s", body="b", status="draft"
        )
        await session.commit()
        thread_id, message_id = thread.id, message.id

    async with AsyncSessionLocal() as session:
        message = await approve_outreach_message(session, message_id=message_id)
        await session.commit()
    assert message.status == "approved"

    async with AsyncSessionLocal() as session:
        thread = await get_outreach_thread(session, creator_id=creator_id, thread_id=thread_id)
    assert thread.status == "approved"


async def test_cannot_approve_a_message_twice():
    creator_id = await _make_creator()
    opportunity_id = await _make_scored_opportunity(creator_id)

    async with AsyncSessionLocal() as session:
        thread = await create_outreach_thread(session, creator_id=creator_id, brand_opportunity_id=opportunity_id)
        message = await add_outreach_message(
            session, thread_id=thread.id, direction="outbound", kind="initial_pitch", subject="s", body="b", status="draft"
        )
        await session.commit()
        message_id = message.id

    async with AsyncSessionLocal() as session:
        await approve_outreach_message(session, message_id=message_id)
        await session.commit()

    async with AsyncSessionLocal() as session:
        with pytest.raises(ValueError, match="Cannot approve"):
            await approve_outreach_message(session, message_id=message_id)


async def test_cannot_mark_sent_before_approved():
    """The human-in-the-loop gate (CLAUDE.md §70): a draft can never be
    marked sent by skipping approval, no matter who calls this."""
    creator_id = await _make_creator()
    opportunity_id = await _make_scored_opportunity(creator_id)

    async with AsyncSessionLocal() as session:
        thread = await create_outreach_thread(session, creator_id=creator_id, brand_opportunity_id=opportunity_id)
        message = await add_outreach_message(
            session, thread_id=thread.id, direction="outbound", kind="initial_pitch", subject="s", body="b", status="draft"
        )
        await session.commit()
        message_id = message.id

    async with AsyncSessionLocal() as session:
        with pytest.raises(ValueError, match="Cannot mark sent"):
            await mark_outreach_message_sent(session, message_id=message_id)


async def test_mark_sent_after_approval_advances_thread_and_sets_sent_at():
    creator_id = await _make_creator()
    opportunity_id = await _make_scored_opportunity(creator_id)

    async with AsyncSessionLocal() as session:
        thread = await create_outreach_thread(session, creator_id=creator_id, brand_opportunity_id=opportunity_id)
        message = await add_outreach_message(
            session, thread_id=thread.id, direction="outbound", kind="initial_pitch", subject="s", body="b", status="draft"
        )
        await session.commit()
        thread_id, message_id = thread.id, message.id

    async with AsyncSessionLocal() as session:
        await approve_outreach_message(session, message_id=message_id)
        await session.commit()

    async with AsyncSessionLocal() as session:
        message = await mark_outreach_message_sent(session, message_id=message_id)
        await session.commit()
    assert message.status == "sent"
    assert message.sent_at is not None

    async with AsyncSessionLocal() as session:
        thread = await get_outreach_thread(session, creator_id=creator_id, thread_id=thread_id)
    assert thread.status == "sent"


async def test_follow_up_message_does_not_advance_thread_status():
    """Only the initial pitch's approve/send transitions drive the thread's
    own pipeline stage — a follow-up is additional correspondence within an
    already-sent thread, not a new pipeline stage of its own."""
    creator_id = await _make_creator()
    opportunity_id = await _make_scored_opportunity(creator_id)

    async with AsyncSessionLocal() as session:
        thread = await create_outreach_thread(session, creator_id=creator_id, brand_opportunity_id=opportunity_id)
        initial = await add_outreach_message(
            session, thread_id=thread.id, direction="outbound", kind="initial_pitch", subject="s", body="b", status="draft"
        )
        await session.commit()
        thread_id = thread.id

    async with AsyncSessionLocal() as session:
        await approve_outreach_message(session, message_id=initial.id)
        await mark_outreach_message_sent(session, message_id=initial.id)
        await session.commit()

    async with AsyncSessionLocal() as session:
        follow_up = await add_outreach_message(
            session, thread_id=thread_id, direction="outbound", kind="follow_up", subject="s2", body="b2", status="draft"
        )
        await session.commit()
        follow_up_id = follow_up.id

    async with AsyncSessionLocal() as session:
        await approve_outreach_message(session, message_id=follow_up_id)
        await mark_outreach_message_sent(session, message_id=follow_up_id)
        await session.commit()

    async with AsyncSessionLocal() as session:
        thread = await get_outreach_thread(session, creator_id=creator_id, thread_id=thread_id)
    assert thread.status == "sent"


async def test_get_outreach_message_is_scoped_to_thread():
    creator_id = await _make_creator()
    opportunity_id = await _make_scored_opportunity(creator_id)

    async with AsyncSessionLocal() as session:
        thread_a = await create_outreach_thread(session, creator_id=creator_id, brand_opportunity_id=opportunity_id)
        await session.commit()
        message = await add_outreach_message(
            session, thread_id=thread_a.id, direction="outbound", kind="initial_pitch", subject="s", body="b", status="draft"
        )
        await session.commit()
        message_id = message.id

    async with AsyncSessionLocal() as session:
        found_in_own_thread = await get_outreach_message(session, thread_id=thread_a.id, message_id=message_id)
        found_in_wrong_thread = await get_outreach_message(session, thread_id="othread_wrong", message_id=message_id)

    assert found_in_own_thread is not None
    assert found_in_wrong_thread is None
