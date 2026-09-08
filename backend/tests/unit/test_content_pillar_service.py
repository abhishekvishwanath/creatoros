from sqlalchemy import select

from app.domain.content.models import ContentPillar
from app.domain.content.service import sync_content_pillars
from app.domain.creator.models import Creator, User
from app.infrastructure.db.session import AsyncSessionLocal


async def _make_creator() -> str:
    async with AsyncSessionLocal() as session:
        user = User(email="pillartest@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Pillar Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def test_sync_creates_new_pillars():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await sync_content_pillars(
            session,
            creator_id=creator_id,
            pillars=[{"name": "Budgeting", "description": "Money basics"}],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ContentPillar).where(ContentPillar.creator_id == creator_id))
        pillars = result.scalars().all()
    assert len(pillars) == 1
    assert pillars[0].name == "Budgeting"


async def test_sync_updates_existing_pillar_by_case_insensitive_name_instead_of_duplicating():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await sync_content_pillars(
            session, creator_id=creator_id, pillars=[{"name": "Budgeting", "description": "v1"}]
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        await sync_content_pillars(
            session, creator_id=creator_id, pillars=[{"name": "budgeting", "description": "v2"}]
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ContentPillar).where(ContentPillar.creator_id == creator_id))
        pillars = result.scalars().all()
    assert len(pillars) == 1
    assert pillars[0].description == "v2"


async def test_sync_merges_near_duplicate_names_within_the_same_proposal():
    """Regression test: a model proposing both 'Budgeting' and 'budgeting' in
    the same batch must not create two rows that no later run could ever
    merge back together (matching only happens against the DB read at the
    start of sync_content_pillars)."""
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await sync_content_pillars(
            session,
            creator_id=creator_id,
            pillars=[
                {"name": "Budgeting", "description": "v1"},
                {"name": "budgeting", "description": "v2"},
            ],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ContentPillar).where(ContentPillar.creator_id == creator_id))
        pillars = result.scalars().all()
    assert len(pillars) == 1
    assert pillars[0].description == "v2"


async def test_sync_never_deletes_a_pillar_missing_from_the_new_proposal():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await sync_content_pillars(
            session, creator_id=creator_id, pillars=[{"name": "Budgeting", "description": "d"}]
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        await sync_content_pillars(
            session, creator_id=creator_id, pillars=[{"name": "Investing", "description": "d2"}]
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ContentPillar).where(ContentPillar.creator_id == creator_id))
        names = {p.name for p in result.scalars().all()}
    assert names == {"Budgeting", "Investing"}
