"""Brand database (CLAUDE.md §68-69, Part II Phase 2).

Manual entry only — no company-database/enrichment API is wired in (see
CLAUDE.md §69 for why that's a deliberate MVP choice, not an oversight).
Every route below that touches a specific brand's sub-resources (contacts,
signals) re-verifies the brand belongs to this creator first — BrandContact/
BrandSignal aren't creator-scoped columns themselves, so that check is the
only thing standing between one creator and another creator's contacts.
"""

from fastapi import APIRouter, Depends, HTTPException, status

from app.agent_service.agents.brand_intelligence import BrandIntelligenceAgent
from app.agent_service.agents.campaign_intelligence import CampaignIntelligenceAgent
from app.agent_service.agents.outreach import OutreachAgent
from app.agent_service.context.builder import (
    build_brand_opportunity_context,
    build_campaign_brief_context,
    build_creator_state_snapshot,
    build_outreach_context,
)
from app.agent_service.model_router.router import get_model_router
from app.agent_service.orchestrator.orchestrator import Orchestrator
from app.api.deps import DbSession, get_owned_creator, validate_or_502
from app.domain.commercial.models import Brand, BrandContact, BrandOpportunity, BrandSignal
from app.domain.commercial.service import (
    add_brand_contact,
    add_brand_signal,
    apply_brand_opportunity_score,
    apply_campaign_brief,
    create_brand,
    create_outreach_thread,
    add_outreach_message,
    get_brand,
    get_brand_contact,
    get_brand_opportunity_by_id,
    get_campaign_brief,
    list_brand_contacts,
    list_brand_opportunities,
    list_brand_signals,
    list_brands,
)
from app.domain.creator.models import Creator
from app.schemas.commercial import (
    BrandContactCreate,
    BrandContactRead,
    BrandCreate,
    BrandOpportunityRead,
    BrandRadarItem,
    BrandRead,
    BrandSignalCreate,
    BrandSignalRead,
    CampaignBriefRead,
    CreateOutreachThreadRequest,
    CreateOutreachThreadResponse,
    GenerateCampaignBriefResponse,
    OutreachMessageRead,
    OutreachThreadRead,
    ScoreBrandOpportunityResponse,
)

router = APIRouter(prefix="/creators/{creator_id}/brands", tags=["brands"])
radar_router = APIRouter(prefix="/creators/{creator_id}/brand-opportunities", tags=["brands"])


async def _get_owned_brand(db: DbSession, creator: Creator, brand_id: str) -> Brand:
    brand = await get_brand(db, creator_id=creator.id, brand_id=brand_id)
    if brand is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand not found")
    return brand


@router.post("", response_model=BrandRead, status_code=201)
async def create_brand_route(
    payload: BrandCreate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> Brand:
    brand = await create_brand(db, creator_id=creator.id, data=payload.model_dump())
    await db.commit()
    await db.refresh(brand)
    return brand


@router.get("", response_model=list[BrandRead])
async def list_brands_route(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> list[Brand]:
    return await list_brands(db, creator_id=creator.id)


@router.get("/{brand_id}", response_model=BrandRead)
async def get_brand_route(
    brand_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> Brand:
    return await _get_owned_brand(db, creator, brand_id)


@router.post("/{brand_id}/contacts", response_model=BrandContactRead, status_code=201)
async def add_brand_contact_route(
    brand_id: str,
    payload: BrandContactCreate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> BrandContact:
    await _get_owned_brand(db, creator, brand_id)
    contact = await add_brand_contact(db, brand_id=brand_id, data=payload.model_dump())
    await db.commit()
    await db.refresh(contact)
    return contact


@router.get("/{brand_id}/contacts", response_model=list[BrandContactRead])
async def list_brand_contacts_route(
    brand_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> list[BrandContact]:
    await _get_owned_brand(db, creator, brand_id)
    return await list_brand_contacts(db, brand_id=brand_id)


@router.post("/{brand_id}/signals", response_model=BrandSignalRead, status_code=201)
async def add_brand_signal_route(
    brand_id: str,
    payload: BrandSignalCreate,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> BrandSignal:
    await _get_owned_brand(db, creator, brand_id)
    signal = await add_brand_signal(db, creator_id=creator.id, brand_id=brand_id, data=payload.model_dump())
    await db.commit()
    await db.refresh(signal)
    return signal


@router.get("/{brand_id}/signals", response_model=list[BrandSignalRead])
async def list_brand_signals_route(
    brand_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> list[BrandSignal]:
    await _get_owned_brand(db, creator, brand_id)
    return await list_brand_signals(db, creator_id=creator.id, brand_id=brand_id)


@router.post("/{brand_id}/opportunities/score", response_model=ScoreBrandOpportunityResponse)
async def score_brand_opportunity_route(
    brand_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> ScoreBrandOpportunityResponse:
    brand = await _get_owned_brand(db, creator, brand_id)
    brand_context = await build_brand_opportunity_context(db, brand)
    creator_snapshot = await build_creator_state_snapshot(db, creator)

    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    output = await orchestrator.run_agent(
        agent=BrandIntelligenceAgent(),
        creator_id=creator.id,
        workflow_name="brand_opportunity_scoring",
        context=creator_snapshot,
        brand=brand_context["brand"],
        signals=brand_context["signals"],
        existing_contact_roles=brand_context["existing_contact_roles"],
        contactability=brand_context["contactability"],
    )

    if output.status == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=output.summary + ("; " + "; ".join(output.warnings) if output.warnings else ""),
        )

    opportunity_read = None
    for change in output.proposed_state_changes:
        if change.get("type") == "brand_opportunity_score":
            score_data = change["data"]
            opportunity = await apply_brand_opportunity_score(
                db,
                creator_id=creator.id,
                brand_id=brand_id,
                score_components=score_data.get("score_components", {}),
                contactability=brand_context["contactability"],
                reasons=score_data.get("reasons", ""),
                evidence_signal_ids=score_data.get("evidence_signal_ids", []),
                suggested_contact_roles=score_data.get("suggested_contact_roles", []),
                confidence=change.get("confidence", 0.0),
                prohibited_conflict=score_data.get("prohibited_conflict", False),
            )
            opportunity_read = validate_or_502(BrandOpportunityRead, opportunity, label="Brand Intelligence")

    await db.commit()
    return ScoreBrandOpportunityResponse(opportunity=opportunity_read, warnings=output.warnings)


@radar_router.get("", response_model=list[BrandRadarItem])
async def list_brand_radar(
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> list[BrandRadarItem]:
    rows = await list_brand_opportunities(db, creator_id=creator.id)
    return [BrandRadarItem(brand=brand, opportunity=opportunity) for opportunity, brand in rows]


async def _get_owned_opportunity(db: DbSession, creator: Creator, opportunity_id: str) -> BrandOpportunity:
    opportunity = await get_brand_opportunity_by_id(db, creator_id=creator.id, opportunity_id=opportunity_id)
    if opportunity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Brand opportunity not found")
    return opportunity


@radar_router.get("/{opportunity_id}/campaign-brief", response_model=CampaignBriefRead | None)
async def get_campaign_brief_route(
    opportunity_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
):
    await _get_owned_opportunity(db, creator, opportunity_id)
    return await get_campaign_brief(db, brand_opportunity_id=opportunity_id)


@radar_router.post("/{opportunity_id}/campaign-brief", response_model=GenerateCampaignBriefResponse)
async def generate_campaign_brief_route(
    opportunity_id: str,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> GenerateCampaignBriefResponse:
    opportunity = await _get_owned_opportunity(db, creator, opportunity_id)
    brand = await _get_owned_brand(db, creator, opportunity.brand_id)
    brief_context = await build_campaign_brief_context(db, opportunity, brand)
    creator_snapshot = await build_creator_state_snapshot(db, creator)

    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    output = await orchestrator.run_agent(
        agent=CampaignIntelligenceAgent(),
        creator_id=creator.id,
        workflow_name="campaign_brief_generation",
        context=creator_snapshot,
        brand=brief_context["brand"],
        signals=brief_context["signals"],
        opportunity=brief_context["opportunity"],
    )

    if output.status == "failed":
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY,
            detail=output.summary + ("; " + "; ".join(output.warnings) if output.warnings else ""),
        )

    brief_read = None
    for change in output.proposed_state_changes:
        if change.get("type") == "campaign_brief_upsert":
            brief_data = change["data"]
            brief = await apply_campaign_brief(
                db,
                brand_opportunity_id=opportunity_id,
                data=brief_data,
                evidence_signal_ids=brief_data.get("evidence_signal_ids", []),
                confidence=change.get("confidence", 0.0),
            )
            brief_read = validate_or_502(CampaignBriefRead, brief, label="Campaign Intelligence")

    await db.commit()
    return GenerateCampaignBriefResponse(brief=brief_read, warnings=output.warnings)


@radar_router.post("/{opportunity_id}/outreach", response_model=CreateOutreachThreadResponse, status_code=201)
async def create_outreach_thread_route(
    opportunity_id: str,
    payload: CreateOutreachThreadRequest,
    db: DbSession,
    creator: Creator = Depends(get_owned_creator),
) -> CreateOutreachThreadResponse:
    """Starts a new outreach thread and drafts its initial pitch in one
    step. Nothing is persisted unless the agent actually produced a usable
    draft (CLAUDE.md §43 — no half-successful state that looks valid): a
    stub-mode skip or a failed draft leaves no thread/message behind, only
    warnings, mirroring the brand-scoring/campaign-brief response shape."""
    opportunity = await _get_owned_opportunity(db, creator, opportunity_id)
    brand = await _get_owned_brand(db, creator, opportunity.brand_id)
    brief = await get_campaign_brief(db, brand_opportunity_id=opportunity_id)
    if brief is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Generate a campaign brief before starting outreach.")

    contact = None
    if payload.contact_id:
        contact = await get_brand_contact(db, brand_id=brand.id, contact_id=payload.contact_id)
        if contact is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found on this brand")

    outreach_context = build_outreach_context(brand, brief, contact)
    creator_snapshot = await build_creator_state_snapshot(db, creator)

    orchestrator = Orchestrator(db=db, model_router=get_model_router())
    output = await orchestrator.run_agent(
        agent=OutreachAgent(),
        creator_id=creator.id,
        workflow_name="outreach_initial_pitch",
        context=creator_snapshot,
        brand=outreach_context["brand"],
        brief=outreach_context["brief"],
        contact=outreach_context["contact"],
        kind="initial_pitch",
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
        return CreateOutreachThreadResponse(thread=None, message=None, warnings=output.warnings)

    thread = await create_outreach_thread(
        db,
        creator_id=creator.id,
        brand_opportunity_id=opportunity_id,
        contact_id=contact.id if contact else None,
        campaign_brief_id=brief.id,
    )
    message = await add_outreach_message(
        db,
        thread_id=thread.id,
        direction="outbound",
        kind="initial_pitch",
        subject=draft_data.get("subject"),
        body=draft_data.get("body", ""),
        status="draft",
    )
    await db.commit()
    return CreateOutreachThreadResponse(
        thread=validate_or_502(OutreachThreadRead, thread, label="Outreach"),
        message=validate_or_502(OutreachMessageRead, message, label="Outreach"),
        warnings=output.warnings,
    )
