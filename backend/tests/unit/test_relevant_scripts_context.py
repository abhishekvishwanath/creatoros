from app.agent_service.context.builder import build_relevant_scripts_context
from app.domain.content.models import ContentItem
from app.domain.creator.models import Creator, User
from app.domain.memory.service import store_embedding
from app.infrastructure.db.session import AsyncSessionLocal


async def _make_creator() -> Creator:
    async with AsyncSessionLocal() as session:
        user = User(email="scriptcontext@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Script Context Test")
        session.add(creator)
        await session.commit()
        await session.refresh(creator)
        return creator


async def test_build_relevant_scripts_context_returns_closest_match_first():
    creator = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_1", creator_id=creator.id, topic="t"))
        session.add(ContentItem(id="cnt_2", creator_id=creator.id, topic="t"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        await store_embedding(
            session,
            creator_id=creator.id,
            content_item_id="cnt_1",
            source_type="script",
            text="A script about how to negotiate a raise at your day job.",
        )
        await store_embedding(
            session,
            creator_id=creator.id,
            content_item_id="cnt_2",
            source_type="script",
            text="A script comparing the best cast iron pans for beginners.",
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        results = await build_relevant_scripts_context(session, creator, "how to ask your boss for a salary increase")
    assert len(results) == 2
    assert "negotiate" in results[0]["text"]


async def test_build_relevant_scripts_context_returns_empty_for_blank_query():
    creator = await _make_creator()
    async with AsyncSessionLocal() as session:
        results = await build_relevant_scripts_context(session, creator, "   ")
    assert results == []


async def test_build_relevant_scripts_context_excludes_other_source_types():
    creator = await _make_creator()
    async with AsyncSessionLocal() as session:
        await store_embedding(session, creator_id=creator.id, source_type="comment", text="A viewer comment about pricing.")
        await session.commit()

    async with AsyncSessionLocal() as session:
        results = await build_relevant_scripts_context(session, creator, "pricing")
    assert results == []
