"""Pipeline orchestration (CLAUDE.md §33 Phase 1->4): the "paste a link,
everything starts" entry point. Chains ingestion -> Creator DNA -> real
research-signal seeding -> Trend Intelligence -> Opportunity Engine ->
Strategy Engine as one FastAPI BackgroundTask.

Each stage already exists as its own inspectable, testable route function —
this module calls them directly (they're plain async functions; `Depends(...)`
defaults are only resolved by FastAPI's DI, not when called as plain Python)
rather than re-implementing their apply-logic a second time (CLAUDE.md §3.7
one source of truth). The background task opens its own DB session since
the request's session is closed once the 202 response is sent.
"""

import logging
from typing import Awaitable, Callable, TypeVar

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status

from app.api.deps import DbSession, get_owned_creator
from app.api.routes.creators import analyze_creator
from app.api.routes.ingestion import import_youtube
from app.api.routes.opportunities import generate_opportunities
from app.api.routes.research import analyze_trends
from app.api.routes.strategy import generate_strategy
from app.domain.creator.models import Creator
from app.domain.pipeline.models import PipelineRun
from app.domain.pipeline.service import complete_run, create_pipeline_run, get_pipeline_run, update_stage
from app.domain.research.auto_seed import auto_seed_research_signals
from app.infrastructure.db.session import AsyncSessionLocal
from app.schemas.ingestion import YoutubeImportRequest
from app.schemas.pipeline import PipelineRunRead, PipelineRunRequest

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/creators/{creator_id}/pipeline", tags=["pipeline"])

T = TypeVar("T")


@router.post("/run", response_model=PipelineRunRead, status_code=202)
async def start_pipeline_run(
    payload: PipelineRunRequest,
    background_tasks: BackgroundTasks,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> PipelineRunRead:
    run = await create_pipeline_run(db, creator_id=creator.id, youtube_url=payload.youtube_url)
    await db.commit()
    background_tasks.add_task(_execute, creator_id=creator.id, run_id=run.id, youtube_url=payload.youtube_url)
    return PipelineRunRead.model_validate(run)


@router.get("/run/{run_id}", response_model=PipelineRunRead)
async def get_pipeline_run_status(
    run_id: str, db: DbSession, creator: Creator = Depends(get_owned_creator)
) -> PipelineRunRead:
    run = await get_pipeline_run(db, creator_id=creator.id, run_id=run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Pipeline run not found")
    return PipelineRunRead.model_validate(run)


async def _stage(
    db,
    run: PipelineRun,
    name: str,
    factory: Callable[[], Awaitable[T]],
    summarize: Callable[[T], tuple[str, list[str]]],
) -> None:
    """Runs one stage, always leaving it in a terminal status — a stage
    failing (bad input, transient model error) never aborts the rest of the
    pipeline, since every downstream stage already degrades gracefully on
    missing input (CLAUDE.md §43) rather than hard-requiring the previous
    one to have succeeded."""
    await update_stage(db, run=run, name=name, status="running")
    await db.commit()
    try:
        result = await factory()
        summary, warnings = summarize(result)
        await update_stage(db, run=run, name=name, status="success", summary=summary, warnings=warnings)
    except HTTPException as exc:
        await update_stage(db, run=run, name=name, status="failed", summary=str(exc.detail))
    except Exception as exc:  # noqa: BLE001 - a background task must never crash silently
        logger.warning("Pipeline stage %r failed for run %s", name, run.id, exc_info=True)
        await update_stage(db, run=run, name=name, status="failed", summary=str(exc))
    await db.commit()


async def _execute(*, creator_id: str, run_id: str, youtube_url: str | None) -> None:
    async with AsyncSessionLocal() as db:
        run = await get_pipeline_run(db, creator_id=creator_id, run_id=run_id)
        creator = await db.get(Creator, creator_id)
        if run is None or creator is None:
            return

        try:
            await _run_all_stages(db, run, creator, youtube_url)
            await complete_run(db, run=run, status="completed")
        except Exception as exc:  # noqa: BLE001 - a run must never hang at "running" forever
            logger.error("Pipeline run %s failed outside stage handling", run_id, exc_info=True)
            await complete_run(db, run=run, status="failed", error=str(exc))
        await db.commit()


async def _run_all_stages(db, run: PipelineRun, creator: Creator, youtube_url: str | None) -> None:
    if youtube_url:
        await _stage(
            db,
            run,
            "import",
            lambda: import_youtube(YoutubeImportRequest(url=youtube_url), db, creator),
            lambda r: (f"Imported {r.imported_count} video(s) from {r.channel_name}.", r.warnings),
        )
    else:
        await update_stage(db, run=run, name="import", status="skipped", summary="No YouTube URL given.")
        await db.commit()

    await _stage(
        db,
        run,
        "creator_dna",
        lambda: analyze_creator(db, creator),
        lambda r: (
            f"Positioning built"
            + (", voice inferred" if r.state.voice else "")
            + f", {len(r.state.content_pillars)} content pillar(s).",
            r.warnings,
        ),
    )

    await _stage(
        db,
        run,
        "research",
        lambda: auto_seed_research_signals(db, creator=creator),
        lambda signals: (f"Found {len(signals)} real research signal(s) from YouTube.", []),
    )

    await _stage(
        db,
        run,
        "trends",
        lambda: analyze_trends(db, creator),
        lambda r: (f"{len(r.insights)} trend insight(s) analyzed.", r.warnings),
    )

    await _stage(
        db,
        run,
        "opportunities",
        lambda: generate_opportunities(db, creator),
        lambda r: (
            f"{len(r.opportunities)} opportunit{'y' if len(r.opportunities) == 1 else 'ies'} scored.",
            r.warnings,
        ),
    )

    await _stage(
        db,
        run,
        "strategy",
        lambda: generate_strategy(db, creator),
        lambda r: (
            f"Strategy generated with {len(r.strategy.items)} item(s)." if r.strategy else "No strategy generated.",
            r.warnings,
        ),
    )
