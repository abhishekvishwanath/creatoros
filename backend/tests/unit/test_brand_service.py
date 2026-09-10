from app.domain.commercial.service import (
    add_brand_contact,
    add_brand_signal,
    create_brand,
    get_brand,
    list_brand_contacts,
    list_brand_signals,
    list_brands,
)
from app.domain.creator.models import Creator, User
from app.infrastructure.db.session import AsyncSessionLocal

_creator_counter = 0


async def _make_creator() -> str:
    global _creator_counter
    _creator_counter += 1
    async with AsyncSessionLocal() as session:
        user = User(email=f"brand{_creator_counter}@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Brand Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def test_create_brand_defaults_to_creator_provided_and_candidate_status():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        brand = await create_brand(session, creator_id=creator_id, data={"name": "Notion"})
        await session.commit()
    assert brand.source == "creator_provided"
    assert brand.status == "candidate"
    assert brand.confidence == 1.0


async def test_list_brands_is_scoped_to_creator():
    creator_a = await _make_creator()
    creator_b = await _make_creator()
    async with AsyncSessionLocal() as session:
        await create_brand(session, creator_id=creator_a, data={"name": "Notion"})
        await session.commit()

    async with AsyncSessionLocal() as session:
        brands_a = await list_brands(session, creator_id=creator_a)
        brands_b = await list_brands(session, creator_id=creator_b)
    assert len(brands_a) == 1
    assert brands_b == []


async def test_get_brand_returns_none_for_wrong_creator():
    creator_a = await _make_creator()
    creator_b = await _make_creator()
    async with AsyncSessionLocal() as session:
        brand = await create_brand(session, creator_id=creator_a, data={"name": "Notion"})
        await session.commit()
        brand_id = brand.id

    async with AsyncSessionLocal() as session:
        result = await get_brand(session, creator_id=creator_b, brand_id=brand_id)
    assert result is None


async def test_add_and_list_brand_contacts():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        brand = await create_brand(session, creator_id=creator_id, data={"name": "Notion"})
        await session.commit()
        brand_id = brand.id

    async with AsyncSessionLocal() as session:
        contact = await add_brand_contact(
            session, brand_id=brand_id, data={"name": "Jane Doe", "role": "Creator Partnerships"}
        )
        await session.commit()
    assert contact.verification_state == "unverified"
    assert contact.confidence == 0.5

    async with AsyncSessionLocal() as session:
        contacts = await list_brand_contacts(session, brand_id=brand_id)
    assert len(contacts) == 1
    assert contacts[0].name == "Jane Doe"


async def test_add_and_list_brand_signals_scoped_to_brand():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        brand_a = await create_brand(session, creator_id=creator_id, data={"name": "Notion"})
        brand_b = await create_brand(session, creator_id=creator_id, data={"name": "Linear"})
        await session.commit()
        brand_a_id, brand_b_id = brand_a.id, brand_b.id

    async with AsyncSessionLocal() as session:
        await add_brand_signal(
            session, creator_id=creator_id, brand_id=brand_a_id, data={"summary": "Launched a creator program"}
        )
        await add_brand_signal(
            session, creator_id=creator_id, brand_id=brand_b_id, data={"summary": "Hired an influencer marketer"}
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        signals_a = await list_brand_signals(session, creator_id=creator_id, brand_id=brand_a_id)
        all_signals = await list_brand_signals(session, creator_id=creator_id)
    assert len(signals_a) == 1
    assert signals_a[0].summary == "Launched a creator program"
    assert len(all_signals) == 2


async def test_brand_signal_defaults_evidence_quality_to_medium():
    """Mirrors ResearchSignal's rationale: a real human-observed signal, not
    machine-verified against the platform (CLAUDE.md §16)."""
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        signal = await add_brand_signal(
            session, creator_id=creator_id, brand_id=None, data={"summary": "Something happened"}
        )
        await session.commit()
    assert signal.evidence_quality == "medium"
    assert signal.brand_id is None
