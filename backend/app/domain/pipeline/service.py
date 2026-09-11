"""Pipeline run state service (CLAUDE.md §8.3 pattern applied to
orchestration progress rather than agent output). `stages` is a JSON list on
the row — reassigned wholesale (not mutated in place) on every update so
SQLAlchemy's change-tracking for JSON columns reliably detects it."""

from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import generate_id
from app.domain.pipeline.models import PIPELINE_STAGE_NAMES, PipelineRun


async def create_pipeline_run(db: AsyncSession, *, creator_id: str, youtube_url: Optional[str]) -> PipelineRun:
    run = PipelineRun(
        id=generate_id("pipeline_run"),
        creator_id=creator_id,
        status="running",
        youtube_url=youtube_url,
        stages=[{"name": name, "status": "pending", "summary": None, "warnings": []} for name in PIPELINE_STAGE_NAMES],
    )
    db.add(run)
    await db.flush()
    return run


async def update_stage(
    db: AsyncSession,
    *,
    run: PipelineRun,
    name: str,
    status: str,
    summary: Optional[str] = None,
    warnings: Optional[list[str]] = None,
) -> PipelineRun:
    new_stages = []
    for stage in run.stages:
        if stage["name"] == name:
            new_stages.append({"name": name, "status": status, "summary": summary, "warnings": warnings or []})
        else:
            new_stages.append(stage)
    run.stages = new_stages
    await db.flush()
    return run


async def complete_run(db: AsyncSession, *, run: PipelineRun, status: str, error: Optional[str] = None) -> PipelineRun:
    run.status = status
    run.error = error
    await db.flush()
    return run


async def get_pipeline_run(db: AsyncSession, *, creator_id: str, run_id: str) -> Optional[PipelineRun]:
    result = await db.execute(
        select(PipelineRun).where(PipelineRun.id == run_id, PipelineRun.creator_id == creator_id)
    )
    return result.scalar_one_or_none()
