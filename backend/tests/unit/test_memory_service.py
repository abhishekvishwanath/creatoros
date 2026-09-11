from app.domain.content.models import ContentEmbedding, ContentItem
from app.domain.creator.models import Creator, User
from app.domain.memory.service import semantic_search, store_embedding
from app.infrastructure.db.session import AsyncSessionLocal
from sqlalchemy import select


async def _make_creator() -> str:
    async with AsyncSessionLocal() as session:
        user = User(email="memorytest@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Memory Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def test_store_embedding_creates_a_row():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        embedding = await store_embedding(
            session, creator_id=creator_id, source_type="research", text="A note about pricing objections."
        )
        await session.commit()
    assert embedding is not None

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ContentEmbedding).where(ContentEmbedding.creator_id == creator_id))
        rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].source_type == "research"


async def test_store_embedding_upserts_by_content_item_and_source_type():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_fixed", creator_id=creator_id, topic="t"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        await store_embedding(
            session,
            creator_id=creator_id,
            content_item_id="cnt_fixed",
            source_type="script",
            text="First draft of the script.",
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        await store_embedding(
            session,
            creator_id=creator_id,
            content_item_id="cnt_fixed",
            source_type="script",
            text="Rewritten draft of the script.",
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ContentEmbedding).where(ContentEmbedding.creator_id == creator_id))
        rows = result.scalars().all()
    assert len(rows) == 1
    assert rows[0].text == "Rewritten draft of the script."


async def test_semantic_search_ranks_the_closer_match_first():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await store_embedding(
            session,
            creator_id=creator_id,
            source_type="research",
            text="Audiences keep asking about pricing and whether there's a discount.",
        )
        await store_embedding(
            session,
            creator_id=creator_id,
            source_type="research",
            text="A recipe for chocolate chip cookies with brown butter.",
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        results = await semantic_search(session, creator_id=creator_id, query_text="pricing objections from customers")
    assert len(results) == 2
    assert "pricing" in results[0].text


async def test_semantic_search_filters_by_source_type():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await store_embedding(session, creator_id=creator_id, source_type="research", text="A research note about growth.")
        await store_embedding(session, creator_id=creator_id, source_type="learning", text="A learning about growth.")
        await session.commit()

    async with AsyncSessionLocal() as session:
        results = await semantic_search(
            session, creator_id=creator_id, query_text="growth", source_types=["learning"]
        )
    assert len(results) == 1
    assert results[0].source_type == "learning"


async def test_semantic_search_scopes_to_creator():
    creator_id_a = await _make_creator()
    async with AsyncSessionLocal() as session:
        user_b = User(email="memorytest2@example.com")
        session.add(user_b)
        await session.flush()
        creator_b = Creator(user_id=user_b.id, name="Other Creator")
        session.add(creator_b)
        await session.commit()
        creator_id_b = creator_b.id

    async with AsyncSessionLocal() as session:
        await store_embedding(session, creator_id=creator_id_b, source_type="research", text="Only visible to creator B.")
        await session.commit()

    async with AsyncSessionLocal() as session:
        results = await semantic_search(session, creator_id=creator_id_a, query_text="visible to creator B")
    assert results == []
