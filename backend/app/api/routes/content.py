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
from pydantic import BaseModel, ValidationError

from app.agent_service.agents.content_architect import ContentArchitectAgent
from app.agent_service.agents.editorial_critic import EditorialCriticAgent
from app.agent_service.agents.script_agent import ScriptAgent
from app.agent_service.context.builder import build_content_brief_context, build_creator_state_snapshot
from app.agent_service.model_router.router import get_model_router
from app.agent_service.orchestrator.orchestrator import Orchestrator
from app.api.deps import DbSession, get_owned_creator
from app.core.ids import generate_id
from app.domain.content.models import ContentItem
from app.domain.content.service import (
    apply_content_brief,
    apply_critique,
    create_content_item_from_opportunity,
    create_script,
    get_content_brief,
    get_content_item,
    get_script,
    list_scripts,
)
from app.domain.creator.models import Creator
from app.schemas.content import (
    ContentBriefRead,
    ContentDetailRead,
    ContentItemCreate,
    ContentItemFromOpportunityCreate,
    ContentItemRead,
    GenerateBriefResponse,
    GenerateScriptResponse,
    ReviewScriptRequest,
    ReviewScriptResponse,
    ScriptRead,
)

router = APIRouter(prefix="/creators/{creator_id}/content", tags=["content"])


def _validate_or_502(model_cls: type[BaseModel], obj: object, *, label: str) -> BaseModel:
    """The brief/script agents only check that their JSON has the one
    required key `_parse_json` looks for (CLAUDE.md §40 output contracts
    are enforced at the model layer, not guaranteed by the LLM) — a field
    with the wrong shape (e.g. `key_points` returned as a string instead of
    a list) would otherwise reach these `.model_validate()` calls straight
    from a freshly-applied DB write and crash the request with a raw 500.
    Surfacing it as a 502 keeps this on the same "agent produced something
    unusable" path as a parse failure, instead of an unhandled exception."""
    try:
        return model_cls.model_validate(obj)
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"{label} produced an unexpected shape: {exc}"
        ) from exc


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
            brief_read = _validate_or_502(ContentBriefRead, brief, label="Content Architect")

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

    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    output = await orchestrator.run_agent(
        agent=ScriptAgent(),
        creator_id=creator.id,
        workflow_name="script_draft",
        context=snapshot,
        brief=brief_dict,
        platform=item.platform,
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
                content_item_id=content_item_id,
                brief_id=brief.id,
                platform=item.platform,
                body=change["data"]["body"],
                hook_variants=change["data"].get("hook_variants", []),
            )
            script_read = _validate_or_502(ScriptRead, script, label="Script Agent")

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
                            content_item_id=content_item_id,
                            brief_id=script.brief_id,
                            platform=item.platform,
                            body=rewrite_change["data"]["body"],
                            hook_variants=rewrite_change["data"].get("hook_variants", []),
                            status="rewritten",
                        )
                        rewrite_read = _validate_or_502(ScriptRead, rewrite, label="Script Agent (rewrite)")

    await db.commit()
    return ReviewScriptResponse(
        reviewed=_validate_or_502(ScriptRead, script, label="Editorial Critic"),
        rewrite=rewrite_read,
        warnings=warnings,
    )
