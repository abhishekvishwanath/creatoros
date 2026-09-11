"""Research signal auto-seeding (CLAUDE.md §11.3, §17): the bridge between
YouTube ingestion and the Opportunity/Trend engines, which both require real
research signals to have anything to reason over (CLAUDE.md §3.4 — they
correctly refuse to run on nothing, see opportunity_engine.py's early
return). Runs a couple of real YouTube searches against the creator's own
niche/content pillars and writes real ResearchSignal rows through the exact
same path a creator pasting one in by hand would use — no fabricated
evidence, no synthetic signals.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.content.models import ContentPillar
from app.domain.creator.models import Creator
from app.domain.ingestion.youtube_search import search_videos
from app.domain.research.models import ResearchSignal
from app.domain.research.service import ingest_research_signal

AUTO_SEED_MAX_QUERIES = 2
AUTO_SEED_RESULTS_PER_QUERY = 5


async def _build_queries(db: AsyncSession, creator: Creator) -> list[str]:
    queries: list[str] = []
    if creator.niche:
        queries.append(creator.niche)

    pillars_result = await db.execute(
        select(ContentPillar.name).where(ContentPillar.creator_id == creator.id).limit(AUTO_SEED_MAX_QUERIES)
    )
    for (name,) in pillars_result.all():
        if name and name not in queries:
            queries.append(name)

    return queries[:AUTO_SEED_MAX_QUERIES]


async def auto_seed_research_signals(db: AsyncSession, *, creator: Creator) -> list[ResearchSignal]:
    queries = await _build_queries(db, creator)
    if not queries:
        return []

    created: list[ResearchSignal] = []
    for query in queries:
        results = await search_videos(query, limit=AUTO_SEED_RESULTS_PER_QUERY)
        for video in results:
            summary_bits = [video["channel"] or "A creator", f'published "{video["title"]}"']
            if video["views"]:
                summary_bits.append(f'({video["views"]})')
            signal = await ingest_research_signal(
                db,
                creator_id=creator.id,
                data={
                    "topic": query,
                    "subtopic": None,
                    "format": None,
                    "summary": " ".join(summary_bits),
                    "platform": "youtube",
                    "source_url": video["url"],
                    "source_title": video["title"],
                    "engagement": {"views_text": video["views"]} if video["views"] else None,
                },
            )
            created.append(signal)
    return created
