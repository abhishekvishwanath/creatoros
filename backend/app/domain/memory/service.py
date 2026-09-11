"""Semantic memory writes + retrieval (CLAUDE.md §6.2, §10).

This is the only path anything writes to content_embeddings through — every
call site across content/audience/research/experiments ingestion routes
this through store_embedding rather than constructing ContentEmbedding rows
itself, so there is exactly one place that knows how embeddings are
generated (CLAUDE.md §3.7 one source of truth).
"""

import logging
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agent_service.memory.embeddings import embed_text
from app.core.ids import generate_id
from app.domain.content.models import ContentEmbedding

logger = logging.getLogger(__name__)


async def store_embedding(
    db: AsyncSession,
    *,
    creator_id: str,
    source_type: str,
    text: str,
    content_item_id: Optional[str] = None,
) -> Optional[ContentEmbedding]:
    """Embeds `text` and upserts a ContentEmbedding row. Returns None (and
    logs, doesn't raise) if embedding generation failed — the caller's
    primary write already succeeded and must not be rolled back because
    semantic indexing, which is enrichment, couldn't happen (same
    partial-failure discipline as CLAUDE.md §43).

    Upserts by (content_item_id, source_type) when content_item_id is given
    — a script that gets regenerated shouldn't leave stale duplicate
    embeddings behind pointing at superseded text. Sources with no
    content_item_id (a comment, a research observation, a learning) always
    insert a new row, since each occurrence is its own distinct memory.
    """
    vector = embed_text(text)
    if vector is None:
        return None

    embedding: Optional[ContentEmbedding] = None
    if content_item_id is not None:
        result = await db.execute(
            select(ContentEmbedding).where(
                ContentEmbedding.creator_id == creator_id,
                ContentEmbedding.content_item_id == content_item_id,
                ContentEmbedding.source_type == source_type,
            )
        )
        embedding = result.scalar_one_or_none()

    if embedding is not None:
        embedding.text = text
        embedding.embedding = vector
    else:
        embedding = ContentEmbedding(
            id=generate_id("content_embedding"),
            creator_id=creator_id,
            content_item_id=content_item_id,
            source_type=source_type,
            text=text,
            embedding=vector,
        )
        db.add(embedding)

    await db.flush()
    return embedding


async def semantic_search(
    db: AsyncSession,
    *,
    creator_id: str,
    query_text: str,
    source_types: Optional[list[str]] = None,
    limit: int = 5,
) -> list[ContentEmbedding]:
    """Nearest-neighbor retrieval by cosine distance (CLAUDE.md §6.2), the
    "semantically-filtered slice instead of most recent" the Context Builder
    docstrings have flagged as a gap since before this module existed.

    Returns [] (never raises) when the query can't be embedded — every
    caller already has a recency-based fallback available (that's exactly
    what the rest of the Context Builder does), so a degraded embedding
    model should fall back silently rather than break the calling agent.
    """
    query_vector = embed_text(query_text)
    if query_vector is None:
        return []

    query = select(ContentEmbedding).where(ContentEmbedding.creator_id == creator_id)
    if source_types:
        query = query.where(ContentEmbedding.source_type.in_(source_types))
    query = query.order_by(ContentEmbedding.embedding.cosine_distance(query_vector)).limit(limit)

    result = await db.execute(query)
    return list(result.scalars().all())
