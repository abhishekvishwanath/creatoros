from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.agent_service.context.builder import build_creator_state_snapshot
from app.agent_service.model_router.router import get_model_router
from app.agent_service.orchestrator.orchestrator import Orchestrator
from app.agent_service.agents.creator_intelligence import CreatorIntelligenceAgent
from app.api.deps import DbSession, get_owned_creator
from app.domain.creator.models import Creator, User
from app.domain.creator.service import apply_creator_profile_update
from app.schemas.creator import (
    CreatorCreate,
    CreatorCreateResponse,
    CreatorRead,
    CreatorStateSnapshot,
)

router = APIRouter(prefix="/creators", tags=["creators"])


@router.post("", response_model=CreatorCreateResponse, status_code=201)
async def create_creator(payload: CreatorCreate, db: DbSession) -> Creator:
    """Onboarding entry point (CLAUDE.md 33 Phase 1). Finds or creates the
    owning user by email, then creates a new Creator entity under them.

    TODO(auth): once Supabase Auth is wired up, the user will already exist
    (created at signup) and this endpoint will just attach a Creator to the
    authenticated user instead of finding/creating by email.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    if user is None:
        user = User(email=payload.email)
        db.add(user)
        await db.flush()

    creator = Creator(
        user_id=user.id,
        name=payload.name,
        niche=payload.niche,
        sub_niche=payload.sub_niche,
        geography=payload.geography,
        languages=payload.languages,
        business_model=payload.business_model,
        monetization_model=payload.monetization_model,
    )
    db.add(creator)
    await db.commit()
    await db.refresh(creator)
    return creator


@router.get("/{creator_id}", response_model=CreatorRead)
async def get_creator(creator: Creator = Depends(get_owned_creator)) -> Creator:
    return creator


@router.get("/{creator_id}/state", response_model=CreatorStateSnapshot)
async def get_creator_state(db: DbSession, creator: Creator = Depends(get_owned_creator)) -> CreatorStateSnapshot:
    """Creator State Snapshot (CLAUDE.md 32): the bounded working context handed
    to an agent for a task, assembled fresh here from current state rather than
    cached — later phases add recent content / research / experiments / learnings
    once those subsystems exist."""
    return await build_creator_state_snapshot(db, creator)


@router.post("/{creator_id}/analyze", response_model=CreatorStateSnapshot)
async def analyze_creator(db: DbSession, creator: Creator = Depends(get_owned_creator)) -> CreatorStateSnapshot:
    """Runs the Creator Intelligence Agent (CLAUDE.md §11.1) to (re)build this
    creator's positioning. This is the application-service layer: it invokes
    the agent service, then applies whatever it proposes through the domain
    state service — the agent itself never touches the database directly
    (CLAUDE.md §8.3)."""
    snapshot = await build_creator_state_snapshot(db, creator)

    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    agent = CreatorIntelligenceAgent()
    output = await orchestrator.run_agent(
        agent=agent,
        creator_id=creator.id,
        workflow_name="creator_dna_build",
        context=snapshot,
    )

    if output.status == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=output.summary + ("; " + "; ".join(output.warnings) if output.warnings else ""),
        )

    for change in output.proposed_state_changes:
        if change.get("type") == "creator_profile_upsert":
            await apply_creator_profile_update(
                db,
                creator_id=creator.id,
                data=change["data"],
                confidence=output.confidence,
                evidence_ids=output.evidence_ids,
            )

    await db.commit()
    return await build_creator_state_snapshot(db, creator)
