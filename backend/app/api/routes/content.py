"""Content ingestion + Create pipeline (CLAUDE.md §22-24, §33 Phase 6).

Manual entry only for ingestion (no platform OAuth is wired up yet — see
README). The Create pipeline turns an approved opportunity into a content
item, then a brief, then a script, then an editorial critique — mirroring
CLAUDE.md §24's writer → critic → rewriter loop. Each stage is invoked as
its own step (not one combined agent run) since the "Create" page walks the
creator through them one at a time (CLAUDE.md §38) and each stage's output
is meant to be inspected before the next one runs.
"""

from sqlalchemy import desc, select

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.agent_service.agents.content_architect import ContentArchitectAgent
from app.agent_service.agents.editorial_critic import EditorialCriticAgent
from app.agent_service.agents.repurposing import RepurposingAgent
from app.agent_service.agents.script_agent import ScriptAgent
from app.agent_service.context.builder import (
    build_content_brief_context,
    build_creator_state_snapshot,
    build_relevant_scripts_context,
    build_repurposing_context,
)
from app.agent_service.model_router.router import get_model_router
from app.agent_service.orchestrator.orchestrator import Orchestrator
from app.api.deps import DbSession, get_owned_creator, validate_or_502
from app.core.ids import generate_id
from app.domain.content.models import ContentItem
from app.domain.content.service import (
    apply_content_brief,
    apply_critique,
    create_content_item_from_opportunity,
    create_repurposed_content_item,
    create_script,
    get_best_source_text,
    get_content_brief,
    get_content_item,
    get_script,
    list_content_derivatives,
    list_scripts,
    mark_content_stage,
    publish_content_item,
    schedule_content_item,
)
from app.domain.creator.models import Creator
from app.schemas.calendar import (
    CalendarEventRead,
    PublishContentRequest,
    PublishContentResponse,
    ScheduleContentRequest,
    ScheduleContentResponse,
)
from app.schemas.content import (
    ContentBriefRead,
    ContentDetailRead,
    ContentItemCreate,
    ContentItemFromOpportunityCreate,
    ContentItemRead,
    GenerateBriefResponse,
    GenerateScriptResponse,
    RepurposeContentRequest,
    RepurposeContentResponse,
    ReviewScriptRequest,
    ReviewScriptResponse,
    ScriptRead,
)

router = APIRouter(prefix="/creators/{creator_id}/content", tags=["content"])


@router.post("", response_model=ContentItemRead, status_code=201)
async def ingest_content(
    payload: ContentItemCreate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> ContentItem:
    item = ContentItem(
        id=generate_id("content_item"),
        creator_id=creator.id,
        title=payload.title,
        platform=payload.platform,
        format=payload.format,
        topic=payload.topic,
        transcript=payload.transcript,
        source_type="ingested",
        # Manually-entered historical content is already out in the world —
        # PUBLISHED is the honest state, not IDEA (CLAUDE.md §26 state machine).
        status="PUBLISHED",
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return item


@router.get("", response_model=list[ContentItemRead])
async def list_content(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[ContentItem]:
    result = await db.execute(
        select(ContentItem)
        .where(ContentItem.creator_id == creator.id)
        .order_by(desc(ContentItem.created_at))
        .limit(limit)
        .offset(offset)
    )
    return list(result.scalars().all())


@router.post("/from-opportunity", response_model=ContentItemRead, status_code=201)
async def create_from_opportunity(
    payload: ContentItemFromOpportunityCreate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> ContentItem:
    item = await create_content_item_from_opportunity(
        db, creator_id=creator.id, opportunity_id=payload.opportunity_id
    )
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Opportunity not found")
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/{content_item_id}", response_model=ContentDetailRead)
async def get_content_detail(
    content_item_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> ContentDetailRead:
    item = await get_content_item(db, creator_id=creator.id, content_item_id=content_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content item not found")
    brief = await get_content_brief(db, content_item_id=content_item_id)
    scripts = await list_scripts(db, content_item_id=content_item_id)
    return ContentDetailRead(
        item=ContentItemRead.model_validate(item),
        brief=ContentBriefRead.model_validate(brief) if brief else None,
        scripts=[ScriptRead.model_validate(s) for s in scripts],
    )


@router.post("/{content_item_id}/generate-brief", response_model=GenerateBriefResponse)
async def generate_brief(
    content_item_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> GenerateBriefResponse:
    item = await get_content_item(db, creator_id=creator.id, content_item_id=content_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content item not found")

    snapshot = await build_creator_state_snapshot(db, creator)
    brief_context = await build_content_brief_context(db, item)

    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    output = await orchestrator.run_agent(
        agent=ContentArchitectAgent(),
        creator_id=creator.id,
        workflow_name="content_brief",
        context=snapshot,
        content_item=brief_context["content_item"],
        opportunity=brief_context["opportunity"],
        pillar_name=brief_context["pillar_name"],
        evidence_signals=brief_context["evidence_signals"],
    )

    if output.status == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=output.summary + ("; " + "; ".join(output.warnings) if output.warnings else ""),
        )

    brief_read = None
    for change in output.proposed_state_changes:
        if change.get("type") == "content_brief_upsert":
            brief = await apply_content_brief(
                db,
                creator_id=creator.id,
                content_item_id=content_item_id,
                data=change["data"],
                evidence_ids=change.get("evidence_ids", []),
            )
            brief_read = validate_or_502(ContentBriefRead, brief, label="Content Architect")

    await db.commit()
    return GenerateBriefResponse(brief=brief_read, warnings=output.warnings)


@router.post("/{content_item_id}/generate-script", response_model=GenerateScriptResponse)
async def generate_script(
    content_item_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> GenerateScriptResponse:
    item = await get_content_item(db, creator_id=creator.id, content_item_id=content_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content item not found")
    brief = await get_content_brief(db, content_item_id=content_item_id)
    if brief is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Generate a brief before generating a script")

    snapshot = await build_creator_state_snapshot(db, creator)
    brief_dict = ContentBriefRead.model_validate(brief).model_dump()
    query_text = " ".join(filter(None, [brief_dict.get("angle"), brief_dict.get("hook"), brief_dict.get("objective")]))
    reference_scripts = await build_relevant_scripts_context(db, creator, query_text)

    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    output = await orchestrator.run_agent(
        agent=ScriptAgent(),
        creator_id=creator.id,
        workflow_name="script_draft",
        context=snapshot,
        brief=brief_dict,
        platform=item.platform,
        reference_scripts=reference_scripts,
    )

    if output.status == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=output.summary + ("; " + "; ".join(output.warnings) if output.warnings else ""),
        )

    script_read = None
    for change in output.proposed_state_changes:
        if change.get("type") == "script_create":
            script = await create_script(
                db,
                creator_id=creator.id,
                content_item_id=content_item_id,
                brief_id=brief.id,
                platform=item.platform,
                body=change["data"]["body"],
                hook_variants=change["data"].get("hook_variants", []),
            )
            script_read = validate_or_502(ScriptRead, script, label="Script Agent")

    await db.commit()
    return GenerateScriptResponse(script=script_read, warnings=output.warnings)


@router.post("/{content_item_id}/review", response_model=ReviewScriptResponse)
async def review_script(
    content_item_id: str,
    payload: ReviewScriptRequest,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> ReviewScriptResponse:
    """Runs the Editorial Critic on a given script version. A failing
    critique automatically triggers one Script Agent rewrite pass (CLAUDE.md
    §24's writer → critic → rewriter loop) rather than requiring the creator
    to manually re-request generation after every critique."""
    item = await get_content_item(db, creator_id=creator.id, content_item_id=content_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content item not found")
    script = await get_script(db, content_item_id=content_item_id, script_id=payload.script_id)
    if script is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Script not found")
    brief = await get_content_brief(db, content_item_id=content_item_id)

    snapshot = await build_creator_state_snapshot(db, creator)
    brief_dict = ContentBriefRead.model_validate(brief).model_dump() if brief else {}

    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    critique_output = await orchestrator.run_agent(
        agent=EditorialCriticAgent(),
        creator_id=creator.id,
        workflow_name="script_critique",
        context=snapshot,
        script_body=script.body,
        brief=brief_dict,
    )

    if critique_output.status == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=critique_output.summary
            + ("; " + "; ".join(critique_output.warnings) if critique_output.warnings else ""),
        )

    warnings = list(critique_output.warnings)
    rewrite_read = None
    for change in critique_output.proposed_state_changes:
        if change.get("type") == "script_critique":
            critique = change["data"]
            script = await apply_critique(
                db,
                script=script,
                critic_score=critique["score"],
                critic_issues=critique.get("issues", []),
                passed=critique["passed"],
            )

            if not critique["passed"]:
                rewrite_output = await orchestrator.run_agent(
                    agent=ScriptAgent(),
                    creator_id=creator.id,
                    workflow_name="script_rewrite",
                    context=snapshot,
                    brief=brief_dict,
                    platform=item.platform,
                    previous_body=script.body,
                    critic_issues=critique.get("issues", []),
                )
                warnings += rewrite_output.warnings
                for rewrite_change in rewrite_output.proposed_state_changes:
                    if rewrite_change.get("type") == "script_rewrite":
                        rewrite = await create_script(
                            db,
                            creator_id=creator.id,
                            content_item_id=content_item_id,
                            brief_id=script.brief_id,
                            platform=item.platform,
                            body=rewrite_change["data"]["body"],
                            hook_variants=rewrite_change["data"].get("hook_variants", []),
                            status="rewritten",
                        )
                        rewrite_read = validate_or_502(ScriptRead, rewrite, label="Script Agent (rewrite)")

    await db.commit()
    return ReviewScriptResponse(
        reviewed=validate_or_502(ScriptRead, script, label="Editorial Critic"),
        rewrite=rewrite_read,
        warnings=warnings,
    )


@router.post("/{content_item_id}/mark-recorded", response_model=ContentItemRead)
async def mark_recorded(
    content_item_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> ContentItem:
    """Human-reported progress (CLAUDE.md §26) — recording happens off-app,
    so there's nothing for an agent to do beyond letting the creator mark it
    done. See MANUAL_STAGE_TRANSITIONS for why this is optional, not gated."""
    item = await get_content_item(db, creator_id=creator.id, content_item_id=content_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content item not found")
    try:
        item = await mark_content_stage(db, content_item_id=content_item_id, to_status="RECORDED")
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await db.commit()
    await db.refresh(item)
    return item


@router.get("/{content_item_id}/derivatives", response_model=list[ContentItemRead])
async def list_derivatives(
    content_item_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> list[ContentItem]:
    """The content tree grown from this source asset so far (CLAUDE.md §25)."""
    item = await get_content_item(db, creator_id=creator.id, content_item_id=content_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content item not found")
    return await list_content_derivatives(db, creator_id=creator.id, source_content_item_id=content_item_id)


@router.post("/{content_item_id}/repurpose", response_model=RepurposeContentResponse)
async def repurpose_content(
    content_item_id: str,
    payload: RepurposeContentRequest,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> RepurposeContentResponse:
    """Adapts this item's best available source text (a final/critiqued
    script, or the raw ingested transcript) into one platform-native
    derivative (CLAUDE.md §11.9, §25). The derivative is a full ContentItem
    in its own right, born SCRIPTED, that the creator can independently
    critique/schedule/publish."""
    item = await get_content_item(db, creator_id=creator.id, content_item_id=content_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content item not found")

    source_text = await get_best_source_text(db, content_item=item)
    if not source_text:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "This item has no script or transcript yet — generate a script or ingest a transcript before repurposing it.",
        )

    snapshot = await build_creator_state_snapshot(db, creator)
    repurposing_context = build_repurposing_context(item, source_text)

    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    output = await orchestrator.run_agent(
        agent=RepurposingAgent(),
        creator_id=creator.id,
        workflow_name="repurpose_content",
        context=snapshot,
        source_item=repurposing_context["source_item"],
        source_text=repurposing_context["source_text"],
        target_platform=payload.target_platform,
        target_format=payload.target_format,
    )

    if output.status == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=output.summary + ("; " + "; ".join(output.warnings) if output.warnings else ""),
        )

    derivative_read = None
    script_read = None
    caption_concept = None
    transformations: list[str] = []
    for change in output.proposed_state_changes:
        if change.get("type") == "repurposed_content_create":
            data = change["data"]
            derivative, script = await create_repurposed_content_item(
                db,
                creator_id=creator.id,
                source_item=item,
                target_platform=payload.target_platform,
                target_format=payload.target_format,
                title=data.get("title") or item.title or item.topic or "Untitled",
                body=data.get("body", ""),
                hook_variants=data.get("hook_variants", []),
            )
            derivative_read = validate_or_502(ContentItemRead, derivative, label="Repurposing")
            script_read = validate_or_502(ScriptRead, script, label="Repurposing")
            caption_concept = data.get("caption_concept")
            transformations = data.get("transformations", [])

    await db.commit()
    return RepurposeContentResponse(
        derivative=derivative_read,
        script=script_read,
        caption_concept=caption_concept,
        transformations=transformations,
        warnings=output.warnings,
    )


@router.post("/{content_item_id}/mark-editing", response_model=ContentItemRead)
async def mark_editing(
    content_item_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> ContentItem:
    item = await get_content_item(db, creator_id=creator.id, content_item_id=content_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content item not found")
    try:
        item = await mark_content_stage(db, content_item_id=content_item_id, to_status="EDITING")
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await db.commit()
    await db.refresh(item)
    return item


@router.post("/{content_item_id}/schedule", response_model=ScheduleContentResponse)
async def schedule_content(
    content_item_id: str,
    payload: ScheduleContentRequest,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> ScheduleContentResponse:
    item = await get_content_item(db, creator_id=creator.id, content_item_id=content_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content item not found")
    try:
        item, event = await schedule_content_item(
            db, content_item_id=content_item_id, scheduled_at=payload.scheduled_at, platform=payload.platform
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await db.commit()
    await db.refresh(item)
    await db.refresh(event)
    return ScheduleContentResponse(
        item=ContentItemRead.model_validate(item),
        event=CalendarEventRead(
            id=event.id,
            content_item_id=event.content_item_id,
            content_title=item.title,
            content_status=item.status,
            content_format=item.format,
            scheduled_at=event.scheduled_at,
            platform=event.platform,
            status=event.status,
        ),
    )


@router.post("/{content_item_id}/publish", response_model=PublishContentResponse)
async def publish_content(
    content_item_id: str,
    payload: PublishContentRequest,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> PublishContentResponse:
    item = await get_content_item(db, creator_id=creator.id, content_item_id=content_item_id)
    if item is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Content item not found")
    try:
        item, published = await publish_content_item(
            db, content_item_id=content_item_id, url=payload.url, external_id=payload.external_id
        )
    except ValueError as exc:
        raise HTTPException(status.HTTP_409_CONFLICT, str(exc)) from exc
    await db.commit()
    await db.refresh(item)
    return PublishContentResponse(
        item=ContentItemRead.model_validate(item), published_at=published.published_at, url=published.url
    )
