"""Outreach pipeline (CLAUDE.md §66, §70, Part II Phase 6).

Draft-only, human-in-the-loop: the Outreach Agent drafts; a message must be
explicitly approved and then explicitly marked sent by the creator, both
gated in app/domain/commercial/service.py (not just here). Nothing in this
file ever writes to a thread's outcome/creator_decision fields — those
belong to a future creator-decision route (Phase 7), never to an agent and
never to a status-mechanics route like this one (CLAUDE.md §66).
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.agent_service.agents.outreach import OutreachAgent
from app.agent_service.context.builder import (
    build_creator_state_snapshot,
    build_outreach_context,
    build_outreach_followup_context,
)
from app.agent_service.model_router.router import get_model_router
from app.agent_service.orchestrator.orchestrator import Orchestrator
from app.api.deps import DbSession, get_owned_creator, validate_or_502
from app.domain.commercial.models import Brand, OutreachThread
from app.domain.commercial.service import (
    add_outreach_message,
    approve_outreach_message,
    get_brand,
    get_brand_contact,
    get_brand_opportunity_by_id,
    get_campaign_brief,
    get_outreach_message,
    get_outreach_thread,
    list_outreach_messages,
    list_outreach_threads,
    mark_outreach_message_sent,
)
from app.domain.creator.models import Creator
from app.schemas.commercial import (
    DraftFollowUpResponse,
    OutreachMessageRead,
    OutreachPipelineItem,
    OutreachThreadDetail,
    OutreachThreadRead,
)

router = APIRouter(prefix="/creators/{creator_id}/outreach", tags=["outreach"])


async def _get_owned_thread(db: DbSession, creator: Creator, thread_id: str) -> OutreachThread:
    thread = await get_outreach_thread(db, creator_id=creator.id, thread_id=thread_id)
    if thread is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Outreach thread not found")
    return thread


async def _get_thread_brand(db: DbSession, creator: Creator, thread: OutreachThread) -> Brand:
    """Resolves a thread's brand via its opportunity — 404s instead of
    letting a missing row (an inconsistent FK state today, and one Phase 7
    won't rule out either) surface as an unhandled 500, matching every
    owned-resource lookup elsewhere in the commercial routes."""
    opportunity = await get_brand_opportunity_by_id(db, creator_id=creator.id, opportunity_id=thread.brand_opportunity_id)
    if opportunity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This thread's brand opportunity no longer exists")
    brand = await get_brand(db, creator_id=creator.id, brand_id=opportunity.brand_id)
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "This thread's brand no longer exists")
    return brand


@router.get("", response_model=list[OutreachPipelineItem])
async def list_outreach_route(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> list[OutreachPipelineItem]:
    rows = await list_outreach_threads(db, creator_id=creator.id)
    return [OutreachPipelineItem(thread=thread, brand=brand) for thread, brand in rows]


@router.get("/{thread_id}", response_model=OutreachThreadDetail)
async def get_outreach_thread_route(
    thread_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> OutreachThreadDetail:
    thread = await _get_owned_thread(db, creator, thread_id)
    brand = await _get_thread_brand(db, creator, thread)
    messages = await list_outreach_messages(db, thread_id=thread_id)
    return OutreachThreadDetail(thread=thread, brand=brand, messages=messages)


@router.patch("/{thread_id}/messages/{message_id}/approve", response_model=OutreachMessageRead)
async def approve_message_route(
    thread_id: str,
    message_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> OutreachMessageRead:
    await _get_owned_thread(db, creator, thread_id)
    message = await get_outreach_message(db, thread_id=thread_id, message_id=message_id)
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Outreach message not found")
    try:
        message = await approve_outreach_message(db, message_id=message_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await db.commit()
    await db.refresh(message)
    return message


@router.patch("/{thread_id}/messages/{message_id}/mark-sent", response_model=OutreachMessageRead)
async def mark_sent_route(
    thread_id: str,
    message_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> OutreachMessageRead:
    """The creator's own confirmation that they sent this message through
    their own email client — CreatorOS never sends anything itself
    (CLAUDE.md §70). Requires 'approved' first, gated in the service layer."""
    await _get_owned_thread(db, creator, thread_id)
    message = await get_outreach_message(db, thread_id=thread_id, message_id=message_id)
    if message is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Outreach message not found")
    try:
        message = await mark_outreach_message_sent(db, message_id=message_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await db.commit()
    await db.refresh(message)
    return message


@router.post("/{thread_id}/follow-up", response_model=DraftFollowUpResponse)
async def draft_follow_up_route(
    thread_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> DraftFollowUpResponse:
    thread = await _get_owned_thread(db, creator, thread_id)
    if thread.status != "sent":
        # A follow-up only makes sense once the initial pitch has actually
        # gone out — drafting one on a thread still awaiting approval/send
        # (or, once Phase 7 exists, one already closed out) would let the
        # creator draft correspondence for a conversation that, from the
        # brand's side, hasn't started yet.
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"Cannot draft a follow-up from thread status {thread.status!r} (expected 'sent').",
        )
    brand = await _get_thread_brand(db, creator, thread)
    brief = await get_campaign_brief(db, brand_opportunity_id=thread.brand_opportunity_id)
    contact = await get_brand_contact(db, brand_id=brand.id, contact_id=thread.contact_id) if thread.contact_id else None
    if brief is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No campaign brief found for this thread's opportunity.")

    outreach_context = build_outreach_context(brand, brief, contact)
    prior_messages = await build_outreach_followup_context(db, thread_id)
    creator_snapshot = await build_creator_state_snapshot(db, creator)

    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    output = await orchestrator.run_agent(
        agent=OutreachAgent(),
        creator_id=creator.id,
        workflow_name="outreach_follow_up",
        context=creator_snapshot,
        brand=outreach_context["brand"],
        brief=outreach_context["brief"],
        contact=outreach_context["contact"],
        kind="follow_up",
        prior_messages=prior_messages,
    )

    if output.status == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=output.summary + ("; " + "; ".join(output.warnings) if output.warnings else ""),
        )

    draft_data = None
    for change in output.proposed_state_changes:
        if change.get("type") == "outreach_message_draft":
            draft_data = change["data"]

    if draft_data is None:
        return DraftFollowUpResponse(message=None, warnings=output.warnings)

    message = await add_outreach_message(
        db,
        thread_id=thread_id,
        direction="outbound",
        kind="follow_up",
        subject=draft_data.get("subject"),
        body=draft_data.get("body", ""),
        status="draft",
    )
    await db.commit()
    return DraftFollowUpResponse(message=validate_or_502(OutreachMessageRead, message, label="Outreach"), warnings=output.warnings)
