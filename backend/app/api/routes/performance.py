"""Performance ingestion + diagnosis (CLAUDE.md §27-29, §54 items 13-14).

Manual entry only (no live platform-API sync wired up yet, same as content
ingestion and research signals). Ingestion writes a new time-series snapshot
per call rather than overwriting one row, so a piece's performance
trajectory over time (day 1 vs day 7 views) is preserved, not collapsed
into a single point. Diagnosis computes this piece's metrics-vs-baseline
ratios in code (app/domain/performance/service.py::compute_ratios) and
hands only those numbers to the Performance Intelligence Agent, whose job
is the qualitative "what might explain this" read (CLAUDE.md §29).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.agent_service.agents.performance_intelligence import PerformanceIntelligenceAgent
from app.agent_service.context.builder import build_creator_state_snapshot, build_performance_context
from app.agent_service.model_router.router import get_model_router
from app.agent_service.orchestrator.orchestrator import Orchestrator
from app.api.deps import DbSession, get_owned_creator, validate_or_502
from app.domain.content.service import get_content_item
from app.domain.creator.models import Creator
from app.domain.performance.models import PerformanceSnapshot
from app.domain.experiments.service import sync_learnings
from app.domain.performance.service import (
    get_performance_overview,
    ingest_performance_snapshot,
    list_performance_snapshots,
    save_diagnosis,
)
from app.schemas.performance import (
    DiagnoseResponse,
    DiagnosisRead,
    PerformanceOverviewItem,
    PerformanceSnapshotCreate,
    PerformanceSnapshotRead,
)

router = APIRouter(prefix="/creators/{creator_id}/content/{content_item_id}/performance", tags=["performance"])
overview_router = APIRouter(prefix="/creators/{creator_id}/performance", tags=["performance"])


@router.post("", response_model=PerformanceSnapshotRead, status_code=201)
async def ingest_performance(
    content_item_id: str,
    payload: PerformanceSnapshotCreate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> PerformanceSnapshot:
    item = await get_content_item(db, creator_id=creator.id, content_item_id=content_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content item not found")
    try:
        snapshot = await ingest_performance_snapshot(
            db, creator_id=creator.id, content_item=item, data=payload.model_dump(exclude_unset=True)
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await db.commit()
    await db.refresh(snapshot)
    return snapshot


@router.get("", response_model=list[PerformanceSnapshotRead])
async def get_performance(
    content_item_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> list[PerformanceSnapshot]:
    item = await get_content_item(db, creator_id=creator.id, content_item_id=content_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content item not found")
    return await list_performance_snapshots(db, content_item_id=content_item_id)


@router.post("/diagnose", response_model=DiagnoseResponse)
async def diagnose_performance(
    content_item_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> DiagnoseResponse:
    item = await get_content_item(db, creator_id=creator.id, content_item_id=content_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content item not found")

    perf_context = await build_performance_context(db, item)
    snapshot_obj = perf_context["snapshot"]
    if snapshot_obj is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Ingest performance metrics before requesting a diagnosis")

    snapshot_read = PerformanceSnapshotRead.model_validate(snapshot_obj)

    creator_snapshot = await build_creator_state_snapshot(db, creator)
    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    output = await orchestrator.run_agent(
        agent=PerformanceIntelligenceAgent(),
        creator_id=creator.id,
        workflow_name="performance_diagnosis",
        context=creator_snapshot,
        content_item=perf_context["content_item"],
        brief=perf_context["brief"],
        pillar_name=perf_context["pillar_name"],
        snapshot=snapshot_read.model_dump(mode="json"),
        baselines=perf_context["baselines"],
        ratios=perf_context["ratios"],
    )

    if output.status == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=output.summary + ("; " + "; ".join(output.warnings) if output.warnings else ""),
        )

    diagnosis_read = None
    for change in output.proposed_state_changes:
        if change.get("type") == "performance_diagnosis":
            diagnosis_data = change["data"]
            diagnosis_read = validate_or_502(DiagnosisRead, diagnosis_data, label="Performance Intelligence")
            snapshot_obj = await save_diagnosis(
                db, snapshot=snapshot_obj, diagnosis=diagnosis_data, ratios=perf_context["ratios"]
            )
            # CLAUDE.md §60: "next week's strategy already knows what
            # happened last week" — every fresh diagnosis re-evaluates
            # whether any associated factor now has enough corroborating
            # evidence to become a persisted learning (event-driven:
            # performance.analyzed -> learning.created, CLAUDE.md §13).
            await sync_learnings(db, creator_id=creator.id)

    await db.commit()
    await db.refresh(snapshot_obj)
    return DiagnoseResponse(
        snapshot=PerformanceSnapshotRead.model_validate(snapshot_obj),
        diagnosis=diagnosis_read,
        warnings=output.warnings,
    )


@overview_router.get("/overview", response_model=list[PerformanceOverviewItem])
async def get_overview(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> list[PerformanceOverviewItem]:
    rows = await get_performance_overview(db, creator_id=creator.id)
    return [
        PerformanceOverviewItem(
            content_item_id=item.id,
            title=item.title,
            topic=item.topic,
            format=item.format,
            platform=item.platform,
            latest_snapshot=PerformanceSnapshotRead.model_validate(snapshot) if snapshot else None,
        )
        for item, snapshot in rows
    ]
