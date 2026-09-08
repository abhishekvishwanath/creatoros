"""Content ingestion (CLAUDE.md §33 Phase 2, §52 MVP item 4).

Manual entry only for now — no platform OAuth is wired up yet (YouTube/
Instagram/X ingestion is deferred; see README). A creator pastes in past
scripts/captions/transcripts so the Creator Intelligence and future content
understanding agents have real material to work from instead of onboarding
fields alone.
"""

from sqlalchemy import desc, select

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, get_owned_creator
from app.core.ids import generate_id
from app.domain.content.models import ContentItem
from app.domain.creator.models import Creator
from app.schemas.content import ContentItemCreate, ContentItemRead

router = APIRouter(prefix="/creators/{creator_id}/content", tags=["content"])


@router.post("", response_model=ContentItemRead, status_code=201)
async def ingest_content(
    payload: ContentItemCreate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> ContentItem:
    item = ContentItem(
        id=generate_id("content_item"),
        creator_id=creator.id,
        title=payload.title,
        platform=payload.platform,
        format=payload.format,
        topic=payload.topic,
        transcript=payload.transcript,
        source_type="ingested",
        # Manually-entered historical content is already out in the world —
        # PUBLISHED is the honest state, not IDEA (CLAUDE.md §26 state machine).
        status="PUBLISHED",
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.get("", response_model=list[ContentItemRead])
async def list_content(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ContentItem]:
    result = await db.execute(
        select(ContentItem)
        .where(ContentItem.creator_id == creator.id)
        .order_by(desc(ContentItem.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())
