from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select

from app.agent_service.context.builder import build_creator_state_snapshot, build_voice_analysis_transcripts
from app.agent_service.model_router.router import get_model_router
from app.agent_service.orchestrator.orchestrator import Orchestrator
from app.agent_service.agents.creator_intelligence import CreatorIntelligenceAgent
from app.api.deps import DbSession, get_current_user_id, get_owned_creator
from app.core.config import get_settings
from app.domain.content.service import sync_content_pillars
from app.domain.creator.models import Creator
from app.domain.creator.service import apply_creator_profile_update, apply_voice_profile_update, find_or_create_user_by_email
from app.schemas.creator import (
    AnalyzeCreatorResponse,
    CreatorCreate,
    CreatorCreateResponse,
    CreatorRead,
    CreatorStateSnapshot,
)

router = APIRouter(prefix="/creators", tags=["creators"])


@router.post("", response_model=CreatorCreateResponse, status_code=201)
async def create_creator(
    payload: CreatorCreate,
    db: DbSession,
    authorization: Optional[str] = Header(default=None),
    x_debug_user_id: Optional[str] = Header(default=None, alias="X-Debug-User-Id"),
) -> Creator:
    """Onboarding entry point (CLAUDE.md 33 Phase 1): creates a new Creator
    entity under the calling user. Resolves that user the normal
    authenticated way (a Supabase Bearer token, or X-Debug-User-Id when real
    auth isn't configured — see app/api/deps.py::get_current_user_id) with
    one additional fallback: if no credential is present at all *and* real
    auth isn't configured, find-or-create the user by the given email. That
    fallback is what lets local dev and the automated test suite bootstrap
    a brand-new identity from nothing but an email, exactly like before this
    route required authentication at all; it's unreachable once
    SUPABASE_URL is actually set.
    """
    settings = get_settings()
    try:
        user_id = await get_current_user_id(db, authorization=authorization, x_debug_user_id=x_debug_user_id)
    except HTTPException:
        if settings.supabase_url or not payload.email:
            raise
        user = await find_or_create_user_by_email(db, email=payload.email)
        user_id = user.id

    creator = Creator(
        user_id=user_id,
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


@router.get("", response_model=list[CreatorRead])
async def list_my_creators(db: DbSession, user_id: str = Depends(get_current_user_id)) -> list[Creator]:
    """Lets a returning, already-authenticated user find their existing
    creator(s) instead of localStorage being the only record of which
    creator belongs to them (CLAUDE.md §46) — a fresh browser/device with a
    valid Supabase session should never be forced back through onboarding."""
    result = await db.execute(select(Creator).where(Creator.user_id == user_id).order_by(Creator.created_at))
    return list(result.scalars().all())


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
