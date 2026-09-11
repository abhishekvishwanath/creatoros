"""Semantic memory search (CLAUDE.md §6.2) — lets the frontend (or the
creator directly, via a search box) query across everything that's been
embedded for a creator: transcripts, scripts, audience comments, research
observations, and learnings. Read-only; nothing here mutates state."""

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, get_owned_creator
from app.domain.creator.models import Creator
from app.domain.memory.service import semantic_search
from app.schemas.memory import MemorySearchResult

router = APIRouter(prefix="/creators/{creator_id}/memory", tags=["memory"])


@router.get("/search", response_model=list[MemorySearchResult])
async def search_memory(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
    q: str = Query(..., min_length=2),
    limit: int = Query(default=8, ge=1, le=30),
) -> list[MemorySearchResult]:
    matches = await semantic_search(db, creator_id=creator.id, query_text=q, limit=limit)
    return [
        MemorySearchResult(
            id=m.id,
            source_type=m.source_type,
            content_item_id=m.content_item_id,
            text=m.text[:400],
        )
        for m in matches
    ]
