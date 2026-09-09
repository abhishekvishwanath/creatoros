"""Calendar / Content Operations (CLAUDE.md §26, §54 item 12).

Surfaces the content state machine as something the creator can act on:
what's scheduled, and rule-based operational bottlenecks (pipeline backlog,
over-capacity, missed schedule) computed directly from the creator's own
data. No agent/model call here — these are plain counts with no
hallucination risk, so running them through an LLM would violate CLAUDE.md
§3.3 ("intelligence over generation") and §53 ("don't create an agent for
every tiny operation"). Manual production-stage mutations (mark-recorded,
schedule, publish) live on the content router (app/api/routes/content.py)
since they're per-content-item actions, not calendar-wide reads.
"""

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Query

from app.api.deps import DbSession, get_owned_creator
from app.domain.content.service import get_content_bottlenecks, list_calendar_events
from app.domain.creator.models import Creator
from app.domain.creator.service import get_weekly_capacity, set_weekly_capacity
from app.schemas.calendar import BottleneckRead, CalendarEventRead, CapacityRead, CapacityUpdate

router = APIRouter(prefix="/creators/{creator_id}/calendar", tags=["calendar"])
capacity_router = APIRouter(prefix="/creators/{creator_id}/capacity", tags=["capacity"])


@router.get("", response_model=list[CalendarEventRead])
async def get_calendar(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
    start: Optional[datetime] = Query(default=None),
    end: Optional[datetime] = Query(default=None),
) -> list[CalendarEventRead]:
    rows = await list_calendar_events(db, creator_id=creator.id, start=start, end=end)
    return [
        CalendarEventRead(
            id=event.id,
            content_item_id=event.content_item_id,
            content_title=item.title if item else None,
            content_status=item.status if item else None,
            content_format=item.format if item else None,
            scheduled_at=event.scheduled_at,
            platform=event.platform,
            status=event.status,
        )
        for event, item in rows
    ]


@router.get("/bottlenecks", response_model=list[BottleneckRead])
async def get_bottlenecks(db: DbSession, creator: Creator = Depends(get_owned_creator)) -> list[dict]:
    return await get_content_bottlenecks(db, creator_id=creator.id)


@capacity_router.get("", response_model=CapacityRead)
async def get_capacity(db: DbSession, creator: Creator = Depends(get_owned_creator)) -> CapacityRead:
    items_per_week = await get_weekly_capacity(db, creator_id=creator.id)
    return CapacityRead(items_per_week=items_per_week)


@capacity_router.put("", response_model=CapacityRead)
async def update_capacity(
    payload: CapacityUpdate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> CapacityRead:
    await set_weekly_capacity(db, creator_id=creator.id, items_per_week=payload.items_per_week)
    await db.commit()
    return CapacityRead(items_per_week=payload.items_per_week)
