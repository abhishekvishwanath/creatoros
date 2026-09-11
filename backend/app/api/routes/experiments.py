"""Experimentation routes (CLAUDE.md §30, §11.11).

Every important strategic hypothesis should eventually be testable
(CLAUDE.md §31) — this is where a hypothesis becomes a tracked test with
real results, and a completed, retained experiment feeds directly into the
same StrategicLearning table the passive Learning Engine writes to (see
app/domain/experiments/service.py::_promote_experiment_to_learning), so
Strategy/Content Architect see it exactly like any other learning with zero
extra plumbing.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.agent_service.agents.experimentation import ExperimentationAgent
from app.agent_service.context.builder import build_creator_state_snapshot
from app.agent_service.model_router.router import get_model_router
from app.agent_service.orchestrator.orchestrator import Orchestrator
from app.api.deps import DbSession, get_owned_creator, validate_or_502
from app.domain.creator.models import Creator
from app.domain.experiments.models import Experiment
from app.domain.experiments.service import (
    add_experiment_result,
    apply_experiment_evaluation,
    compute_experiment_stats,
    create_experiment,
    get_experiment,
    list_experiment_results,
    list_experiments,
    set_experiment_status,
)
from app.schemas.experiments import (
    EvaluateExperimentResponse,
    ExperimentCreate,
    ExperimentDetailRead,
    ExperimentRead,
    ExperimentResultCreate,
    ExperimentResultRead,
    ExperimentStatusUpdate,
)

router = APIRouter(prefix="/creators/{creator_id}/experiments", tags=["experiments"])


async def _get_owned_experiment(db: DbSession, creator: Creator, experiment_id: str) -> Experiment:
    experiment = await get_experiment(db, creator_id=creator.id, experiment_id=experiment_id)
    if experiment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Experiment not found")
    return experiment


@router.post("", response_model=ExperimentRead, status_code=201)
async def create_experiment_route(
    payload: ExperimentCreate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> Experiment:
    experiment = await create_experiment(db, creator_id=creator.id, **payload.model_dump())
    await db.commit()
    await db.refresh(experiment)
    return experiment


@router.get("", response_model=list[ExperimentRead])
async def list_experiments_route(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> list[Experiment]:
    return await list_experiments(db, creator_id=creator.id)


@router.get("/{experiment_id}", response_model=ExperimentDetailRead)
async def get_experiment_detail_route(
    experiment_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> ExperimentDetailRead:
    experiment = await _get_owned_experiment(db, creator, experiment_id)
    results = await list_experiment_results(db, experiment_id=experiment_id)
    return ExperimentDetailRead(
        experiment=ExperimentRead.model_validate(experiment),
        results=[ExperimentResultRead.model_validate(r) for r in results],
    )


@router.patch("/{experiment_id}/status", response_model=ExperimentRead)
async def update_experiment_status_route(
    experiment_id: str,
    payload: ExperimentStatusUpdate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> Experiment:
    experiment = await _get_owned_experiment(db, creator, experiment_id)
    try:
        experiment = await set_experiment_status(db, experiment=experiment, status=payload.status)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await db.commit()
    await db.refresh(experiment)
    return experiment


@router.post("/{experiment_id}/results", response_model=ExperimentResultRead, status_code=201)
async def add_experiment_result_route(
    experiment_id: str,
    payload: ExperimentResultCreate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> ExperimentResultRead:
    await _get_owned_experiment(db, creator, experiment_id)
    result = await add_experiment_result(db, experiment_id=experiment_id, **payload.model_dump())
    await db.commit()
    await db.refresh(result)
    return result


@router.post("/{experiment_id}/evaluate", response_model=EvaluateExperimentResponse)
async def evaluate_experiment_route(
    experiment_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> EvaluateExperimentResponse:
    """Computes test-vs-control stats in code, then asks the Experimentation
    Agent to judge whether they support the hypothesis (CLAUDE.md §20/§29:
    the model reasons over given numbers, never invents its own)."""
    experiment = await _get_owned_experiment(db, creator, experiment_id)
    results = await list_experiment_results(db, experiment_id=experiment_id)
    stats = compute_experiment_stats(results)

    snapshot = await build_creator_state_snapshot(db, creator)
    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    output = await orchestrator.run_agent(
        agent=ExperimentationAgent(),
        creator_id=creator.id,
        workflow_name="experiment_evaluation",
        context=snapshot,
        hypothesis=experiment.hypothesis,
        variable=experiment.variable,
        control_reference=experiment.control_reference,
        stats=stats,
    )

    if output.status == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=output.summary + ("; " + "; ".join(output.warnings) if output.warnings else ""),
        )

    experiment_read = None
    for change in output.proposed_state_changes:
        if change.get("type") == "experiment_evaluation":
            experiment = await apply_experiment_evaluation(
                db, experiment=experiment, data=change["data"], stats=stats, results=results
            )
            experiment_read = validate_or_502(ExperimentRead, experiment, label="Experimentation")

    await db.commit()
    return EvaluateExperimentResponse(experiment=experiment_read, stats=stats, warnings=output.warnings)
