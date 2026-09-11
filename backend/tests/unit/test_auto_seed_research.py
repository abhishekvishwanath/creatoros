from app.domain.content.models import ContentPillar
from app.domain.creator.models import Creator, User
from app.domain.research import auto_seed as auto_seed_module
from app.domain.research.auto_seed import auto_seed_research_signals
from app.domain.research.models import ResearchSignal
from app.infrastructure.db.session import AsyncSessionLocal
from sqlalchemy import select


async def _make_creator(*, niche: str | None = "tech reviews", email: str = "autoseed@example.com") -> Creator:
    async with AsyncSessionLocal() as session:
        user = User(email=email)
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Auto Seed Test", niche=niche)
        session.add(creator)
        await session.commit()
        await session.refresh(creator)
        return creator


_FAKE_RESULTS = [
    {
        "video_id": "vid1",
        "title": "A great video about the niche",
        "channel": "Some Channel",
        "views": "100,000 views",
        "url": "https://www.youtube.com/watch?v=vid1",
    },
    {
        "video_id": "vid2",
        "title": "Another relevant video",
        "channel": "Another Channel",
        "views": None,
        "url": "https://www.youtube.com/watch?v=vid2",
    },
]


async def test_auto_seed_creates_research_signals_from_niche(monkeypatch):
    creator = await _make_creator()

    async def fake_search_videos(query, *, limit=5):
        return _FAKE_RESULTS

    monkeypatch.setattr(auto_seed_module, "search_videos", fake_search_videos)

    async with AsyncSessionLocal() as session:
        signals = await auto_seed_research_signals(session, creator=creator)
        await session.commit()

    assert len(signals) == 2
    assert all(s.topic == "tech reviews" for s in signals)

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ResearchSignal).where(ResearchSignal.creator_id == creator.id))
        rows = result.scalars().all()
    assert len(rows) == 2


async def test_auto_seed_includes_content_pillar_as_a_second_query(monkeypatch):
    creator = await _make_creator(email="autoseed2@example.com")
    async with AsyncSessionLocal() as session:
        session.add(ContentPillar(creator_id=creator.id, name="Budget Gadgets"))
        await session.commit()

    seen_queries = []

    async def fake_search_videos(query, *, limit=5):
        seen_queries.append(query)
        return _FAKE_RESULTS[:1]

    monkeypatch.setattr(auto_seed_module, "search_videos", fake_search_videos)

    async with AsyncSessionLocal() as session:
        await auto_seed_research_signals(session, creator=creator)
        await session.commit()

    assert seen_queries == ["tech reviews", "Budget Gadgets"]


async def test_auto_seed_returns_empty_when_no_niche_or_pillars(monkeypatch):
    creator = await _make_creator(niche=None, email="autoseed3@example.com")

    async def fake_search_videos(query, *, limit=5):
        raise AssertionError("should never be called when there are no queries")

    monkeypatch.setattr(auto_seed_module, "search_videos", fake_search_videos)

    async with AsyncSessionLocal() as session:
        signals = await auto_seed_research_signals(session, creator=creator)
    assert signals == []
