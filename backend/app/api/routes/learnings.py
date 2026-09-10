"""Learning Engine routes (CLAUDE.md §31, §54 item 15; Part II §72).

Sync is also triggered automatically at the end of POST .../diagnose (content
loop, see routes/performance.py) and PATCH .../outreach/{id}/decision
(commercial loop, see routes/outreach.py) — this manual endpoint exists so
the UI can re-derive learnings from full history without a new diagnosis or
decision (e.g. right after this feature ships, over evidence that already
exists). It re-syncs both loops together: each sync call recomputes its
*complete* current set of qualifying, active clusters (not just what changed
since last time), so the merged result is the full active set for both —
same as a fresh GET would show, not a partial delta.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import DbSession, get_owned_creator
from app.domain.creator.models import Creator
from app.domain.experiments.models import StrategicLearning
from app.domain.experiments.service import (
    list_learnings,
    set_learning_status,
    sync_commercial_learnings,
    sync_learnings,
)
from app.schemas.learning import LearningRead, LearningStatusUpdate

router = APIRouter(prefix="/creators/{creator_id}/learnings", tags=["learnings"])


@router.get("", response_model=list[LearningRead])
async def get_learnings(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
    status_filter: Optional[str] = Query(default="active", alias="status"),
) -> list[StrategicLearning]:
    return await list_learnings(db, creator_id=creator.id, status_filter=status_filter)


@router.post("/sync", response_model=list[LearningRead])
async def sync_creator_learnings(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> list[StrategicLearning]:
    content_learnings = await sync_learnings(db, creator_id=creator.id)
    commercial_learnings = await sync_commercial_learnings(db, creator_id=creator.id)
    await db.commit()
    learnings = content_learnings + commercial_learnings
    for learning in learnings:
        await db.refresh(learning)
    return learnings


@router.patch("/{learning_id}", response_model=LearningRead)
async def update_learning_status(
    learning_id: str,
    payload: LearningStatusUpdate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> StrategicLearning:
    learning = await set_learning_status(db, creator_id=creator.id, learning_id=learning_id, status=payload.status)
    if learning is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Learning not found")
    await db.commit()
    await db.refresh(learning)
    return learning
