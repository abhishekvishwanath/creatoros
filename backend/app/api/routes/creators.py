from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.agent_service.context.builder import build_creator_state_snapshot, build_voice_analysis_transcripts
from app.agent_service.model_router.router import get_model_router
from app.agent_service.orchestrator.orchestrator import Orchestrator
from app.agent_service.agents.creator_intelligence import CreatorIntelligenceAgent
from app.api.deps import DbSession, get_owned_creator
from app.domain.content.service import sync_content_pillars
from app.domain.creator.models import Creator, User
from app.domain.creator.service import apply_creator_profile_update, apply_voice_profile_update
from app.schemas.creator import (
    AnalyzeCreatorResponse,
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


@router.post("/{creator_id}/analyze", response_model=AnalyzeCreatorResponse)
async def analyze_creator(db: DbSession, creator: Creator = Depends(get_owned_creator)) -> AnalyzeCreatorResponse:
    """Runs the Creator Intelligence Agent (CLAUDE.md §11.1) to (re)build this
    creator's positioning and, if enough content has been ingested, voice and
    content pillars. This is the application-service layer: it invokes the
    agent service, then applies whatever it proposes through the domain state
    service — the agent itself never touches the database directly
    (CLAUDE.md §8.3).

    The agent's sub-jobs (positioning, voice, pillars) can fail independently
    (status="partial") — only a total failure (status="failed", nothing to
    apply) is a hard error. A partial failure still commits whatever
    succeeded and returns its warnings so the caller can see exactly what
    didn't happen, rather than that failure being silently absorbed into an
    overall "success" (CLAUDE.md §43)."""
    snapshot = await build_creator_state_snapshot(db, creator)
    voice_transcripts = await build_voice_analysis_transcripts(db, creator)

    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    agent = CreatorIntelligenceAgent()
    output = await orchestrator.run_agent(
        agent=agent,
        creator_id=creator.id,
        workflow_name="creator_dna_build",
        context=snapshot,
        voice_transcripts=voice_transcripts,
    )

    if output.status == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=output.summary + ("; " + "; ".join(output.warnings) if output.warnings else ""),
        )

    # Each change carries its own confidence/evidence_ids (CLAUDE.md §3.4 —
    # positioning and voice are different claims with different evidence, so
    # neither should borrow the other's numbers). proposed_state_changes only
    # ever contains the sub-jobs that actually succeeded.
    for change in output.proposed_state_changes:
        change_type = change.get("type")
        if change_type == "creator_profile_upsert":
            await apply_creator_profile_update(
                db,
                creator_id=creator.id,
                data=change["data"],
                confidence=change.get("confidence", 0.0),
                evidence_ids=change.get("evidence_ids", []),
            )
        elif change_type == "voice_profile_upsert":
            await apply_voice_profile_update(
                db,
                creator_id=creator.id,
                data=change["data"],
                confidence=change.get("confidence", 0.0),
                evidence_ids=change.get("evidence_ids", []),
            )
        elif change_type == "content_pillars_upsert":
            await sync_content_pillars(
                db, creator_id=creator.id, pillars=change["data"].get("pillars", [])
            )

    await db.commit()
    state = await build_creator_state_snapshot(db, creator)
    return AnalyzeCreatorResponse(state=state, warnings=output.warnings)
