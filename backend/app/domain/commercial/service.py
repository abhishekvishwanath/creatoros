"""Commercial state service (CLAUDE.md §67, §8.3): the only path a
commercial-profile update takes into the database, whether it comes from the
creator directly (Phase 1: a manual form, confidence=1.0 — their own stated
facts, not an inference) or later from an agent's proposed update (Phase 3+:
lower confidence, evidence_ids attached, same shape either way).

Versioning/supersede logic is shared with CreatorProfile/VoiceProfile/
AudienceProfile via app/domain/shared/versioned_profile.py rather than
re-derived here (CLAUDE.md §3.7 one source of truth, Part II §65).
"""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import generate_id
from app.domain.commercial.models import (
    Brand,
    BrandContact,
    BrandOpportunity,
    BrandSignal,
    CampaignBrief,
    CommercialProfile,
    OutreachMessage,
    OutreachThread,
)
from app.domain.shared.versioned_profile import apply_versioned_profile_update, get_current_versioned_profile

_PROFILE_FIELDS = (
    "ideal_sponsor_categories",
    "prohibited_categories",
    "target_geographies",
    "preferred_deal_formats",
    "minimum_conditions",
    "exclusivity_constraints",
    "usage_rights_preferences",
    "sponsorship_goals",
    "revenue_goal",
    "brands_to_avoid",
)


async def get_current_commercial_profile(db: AsyncSession, *, creator_id: str) -> Optional[CommercialProfile]:
    return await get_current_versioned_profile(db, CommercialProfile, creator_id)


async def apply_commercial_profile_update(
    db: AsyncSession,
    *,
    creator_id: str,
    data: dict,
    confidence: float = 1.0,
    evidence_ids: Optional[list[str]] = None,
) -> CommercialProfile:
    return await apply_versioned_profile_update(
        db,
        model_cls=CommercialProfile,
        id_prefix="commercial_profile",
        creator_id=creator_id,
        data=data,
        fields=_PROFILE_FIELDS,
        confidence=confidence,
        evidence_ids=evidence_ids or [],
    )


# --- Brand database (CLAUDE.md §68-69, Part II Phase 2) ---------------------
# Plain CRUD, no agent involved — manual entry mirrors ResearchSignal
# ingestion exactly (app/domain/research/service.py::ingest_research_signal).


async def create_brand(db: AsyncSession, *, creator_id: str, data: dict) -> Brand:
    brand = Brand(
        id=generate_id("brand"),
        creator_id=creator_id,
        name=data["name"],
        website=data.get("website"),
        category=data.get("category"),
        subcategory=data.get("subcategory"),
        description=data.get("description"),
        geography=data.get("geography"),
        target_customer=data.get("target_customer"),
        products=data.get("products"),
        positioning=data.get("positioning"),
        competitors=data.get("competitors"),
        source=data.get("source", "creator_provided"),
        confidence=data.get("confidence", 1.0),
    )
    db.add(brand)
    await db.flush()
    return brand


async def list_brands(db: AsyncSession, *, creator_id: str, status: Optional[str] = None) -> list[Brand]:
    query = select(Brand).where(Brand.creator_id == creator_id)
    if status:
        query = query.where(Brand.status == status)
    result = await db.execute(query.order_by(desc(Brand.created_at)))
    return list(result.scalars().all())


async def get_brand(db: AsyncSession, *, creator_id: str, brand_id: str) -> Optional[Brand]:
    result = await db.execute(select(Brand).where(Brand.id == brand_id, Brand.creator_id == creator_id))
    return result.scalar_one_or_none()


async def add_brand_contact(db: AsyncSession, *, brand_id: str, data: dict) -> BrandContact:
    contact = BrandContact(
        id=generate_id("brand_contact"),
        brand_id=brand_id,
        name=data.get("name"),
        role=data.get("role"),
        department=data.get("department"),
        email=data.get("email"),
        profile_url=data.get("profile_url"),
        source=data.get("source"),
        verification_state=data.get("verification_state", "unverified"),
        confidence=data.get("confidence", 0.5),
    )
    db.add(contact)
    await db.flush()
    return contact


async def list_brand_contacts(db: AsyncSession, *, brand_id: str) -> list[BrandContact]:
    result = await db.execute(
        select(BrandContact).where(BrandContact.brand_id == brand_id).order_by(desc(BrandContact.created_at))
    )
    return list(result.scalars().all())


async def get_brand_contact(db: AsyncSession, *, brand_id: str, contact_id: str) -> Optional[BrandContact]:
    result = await db.execute(
        select(BrandContact).where(BrandContact.id == contact_id, BrandContact.brand_id == brand_id)
    )
    return result.scalar_one_or_none()


async def add_brand_signal(db: AsyncSession, *, creator_id: str, brand_id: Optional[str], data: dict) -> BrandSignal:
    signal = BrandSignal(
        id=generate_id("brand_signal"),
        creator_id=creator_id,
        brand_id=brand_id,
        signal_type=data.get("signal_type"),
        summary=data["summary"],
        source_url=data.get("source_url"),
        source_note=data.get("source_note"),
        observed_at=data.get("observed_at"),
        retrieved_at=datetime.now(timezone.utc),
        evidence_quality=data.get("evidence_quality", "medium"),
    )
    db.add(signal)
    await db.flush()
    return signal


async def list_brand_signals(db: AsyncSession, *, creator_id: str, brand_id: Optional[str] = None) -> list[BrandSignal]:
    query = select(BrandSignal).where(BrandSignal.creator_id == creator_id)
    if brand_id:
        query = query.where(BrandSignal.brand_id == brand_id)
    result = await db.execute(query.order_by(desc(BrandSignal.created_at)))
    return list(result.scalars().all())


# --- Brand opportunity scoring (CLAUDE.md §71, Part II Phase 3) -------------

# Canonical set of model-groundable dimensions (CLAUDE.md §71) — defined here,
# not in the agent, so the domain layer (not the agent layer) owns what
# "a complete score" means; brand_intelligence.py imports this rather than
# keeping its own copy.
BRAND_OPPORTUNITY_SCORE_DIMENSIONS = (
    "audience_fit",
    "creator_fit",
    "product_content_fit",
    "timing_signal",
    "historical_category_fit",
)
_NEUTRAL_SCORE = 0.5


async def get_brand_opportunity(db: AsyncSession, *, brand_id: str) -> Optional[BrandOpportunity]:
    result = await db.execute(select(BrandOpportunity).where(BrandOpportunity.brand_id == brand_id))
    return result.scalar_one_or_none()


async def apply_brand_opportunity_score(
    db: AsyncSession,
    *,
    creator_id: str,
    brand_id: str,
    score_components: dict,
    contactability: float,
    reasons: str,
    evidence_signal_ids: list[str],
    suggested_contact_roles: list[str],
    confidence: float,
    prohibited_conflict: bool = False,
) -> BrandOpportunity:
    """Upserts by brand_id (CLAUDE.md §71) — a re-score reflects this
    brand's current best-known fit, not a point-in-time snapshot worth
    versioning the way Creator DNA is (CLAUDE.md §15's versioning rule
    applies to identity/history; a brand's fit score is neither).

    `score_components` may be missing a dimension the agent's grounding
    dropped (out of range, non-numeric, or absent from the model's
    response — see brand_intelligence.py). The combined `score` is always
    averaged over the full fixed dimension set (a missing one counts as a
    neutral 0.5), so two brands are comparable purely on fit rather than on
    how many dimensions each one happened to survive grounding — a brand
    scored on 3 dimensions must not be able to out-rank one honestly scored
    on all 5 just by having fewer numbers to average. `score_components` as
    *stored/displayed* keeps only what was actually grounded (plus the
    always-code-computed `contactability`), preserving CLAUDE.md §20's
    "never show an opaque/invented number" rule for the breakdown shown in
    the UI — the neutral fill-in is used for score math only, never
    presented as if the model scored it.
    """
    complete_dimensions = {
        dim: score_components.get(dim, _NEUTRAL_SCORE) for dim in BRAND_OPPORTUNITY_SCORE_DIMENSIONS
    }
    score = round((sum(complete_dimensions.values()) + contactability) / (len(complete_dimensions) + 1), 3)
    stored_components = {**score_components, "contactability": contactability}

    opportunity = await get_brand_opportunity(db, brand_id=brand_id)
    if opportunity is None:
        opportunity = BrandOpportunity(
            id=generate_id("brand_opportunity"),
            creator_id=creator_id,
            brand_id=brand_id,
        )
        db.add(opportunity)

    opportunity.score = score
    opportunity.score_components = stored_components
    opportunity.reasons = reasons
    opportunity.evidence_signal_ids = evidence_signal_ids
    opportunity.suggested_contact_roles = suggested_contact_roles
    opportunity.confidence = confidence
    opportunity.prohibited_conflict = prohibited_conflict
    await db.flush()
    return opportunity


async def list_brand_opportunities(db: AsyncSession, *, creator_id: str) -> list[tuple[BrandOpportunity, Brand]]:
    """Ranked for the Brand Radar UI — highest score first. Joined with
    Brand so the UI doesn't need a second round trip per card."""
    result = await db.execute(
        select(BrandOpportunity, Brand)
        .join(Brand, Brand.id == BrandOpportunity.brand_id)
        .where(BrandOpportunity.creator_id == creator_id)
        .order_by(desc(BrandOpportunity.score))
    )
    return [(opp, brand) for opp, brand in result.all()]


async def get_brand_opportunity_by_id(
    db: AsyncSession, *, creator_id: str, opportunity_id: str
) -> Optional[BrandOpportunity]:
    result = await db.execute(
        select(BrandOpportunity).where(
            BrandOpportunity.id == opportunity_id, BrandOpportunity.creator_id == creator_id
        )
    )
    return result.scalar_one_or_none()


# --- Campaign intelligence / pitch generation (CLAUDE.md §73, Part II Phase 5) --


async def get_campaign_brief(db: AsyncSession, *, brand_opportunity_id: str) -> Optional[CampaignBrief]:
    result = await db.execute(
        select(CampaignBrief).where(CampaignBrief.brand_opportunity_id == brand_opportunity_id)
    )
    return result.scalar_one_or_none()


async def apply_campaign_brief(
    db: AsyncSession,
    *,
    brand_opportunity_id: str,
    data: dict,
    evidence_signal_ids: list[str],
    confidence: float,
) -> CampaignBrief:
    """One current brief per BrandOpportunity — "Create pitch" again
    regenerates this row in place rather than accumulating duplicates (same
    upsert-by-foreign-key discipline as apply_brand_opportunity_score, whose
    explicit-assignment-on-both-branches style this mirrors)."""
    brief = await get_campaign_brief(db, brand_opportunity_id=brand_opportunity_id)
    if brief is None:
        brief = CampaignBrief(id=generate_id("campaign_brief"), brand_opportunity_id=brand_opportunity_id)
        db.add(brief)

    brief.objective_hypothesis = data.get("objective_hypothesis")
    brief.campaign_concept = data.get("campaign_concept")
    brief.content_format = data.get("content_format")
    brief.why_this_brand = data.get("why_this_brand")
    brief.why_now = data.get("why_now")
    brief.suggested_cta = data.get("suggested_cta")
    brief.suggested_deliverables = data.get("suggested_deliverables")
    brief.pitch_angle = data.get("pitch_angle")
    brief.personalization_facts = data.get("personalization_facts")
    brief.evidence_signal_ids = evidence_signal_ids
    brief.confidence = confidence
    await db.flush()
    return brief


# --- Outreach (CLAUDE.md §66, §70, Part II Phase 6) --------------------------
# Draft-only, human-in-the-loop: CreatorOS never sends anything. A message
# must be explicitly approved, then explicitly marked sent by the creator —
# both gates enforced here (ValueError on an invalid transition), not only
# by the route or the UI, so no future caller can skip them either. The
# Outreach Agent (app/agent_service/agents/outreach.py) only ever produces a
# draft; nothing in this module ever sets status to "approved"/"sent" except
# these two explicit, creator-triggered functions, and nothing here ever
# touches outcome/creator_decision (CLAUDE.md §66 — that's a future route's
# job alone, on an explicit creator decision, never an agent's).

MESSAGE_APPROVABLE_FROM = ("draft",)
MESSAGE_SENDABLE_FROM = ("approved",)


async def create_outreach_thread(
    db: AsyncSession,
    *,
    creator_id: str,
    brand_opportunity_id: str,
    contact_id: Optional[str] = None,
    campaign_brief_id: Optional[str] = None,
) -> OutreachThread:
    thread = OutreachThread(
        id=generate_id("outreach_thread"),
        creator_id=creator_id,
        brand_opportunity_id=brand_opportunity_id,
        contact_id=contact_id,
        campaign_brief_id=campaign_brief_id,
        status="drafting",
    )
    db.add(thread)
    await db.flush()
    return thread


async def get_outreach_thread(db: AsyncSession, *, creator_id: str, thread_id: str) -> Optional[OutreachThread]:
    result = await db.execute(
        select(OutreachThread).where(OutreachThread.id == thread_id, OutreachThread.creator_id == creator_id)
    )
    return result.scalar_one_or_none()


async def list_outreach_threads(db: AsyncSession, *, creator_id: str) -> list[tuple[OutreachThread, Brand]]:
    """Joined with Brand (via BrandOpportunity) for the pipeline board, same
    join-so-the-UI-gets-one-round-trip pattern as list_brand_opportunities."""
    result = await db.execute(
        select(OutreachThread, Brand)
        .join(BrandOpportunity, BrandOpportunity.id == OutreachThread.brand_opportunity_id)
        .join(Brand, Brand.id == BrandOpportunity.brand_id)
        .where(OutreachThread.creator_id == creator_id)
        .order_by(desc(OutreachThread.created_at))
    )
    return [(thread, brand) for thread, brand in result.all()]


async def add_outreach_message(
    db: AsyncSession,
    *,
    thread_id: str,
    direction: str,
    kind: str,
    subject: Optional[str],
    body: str,
    status: Optional[str] = None,
) -> OutreachMessage:
    message = OutreachMessage(
        id=generate_id("outreach_message"),
        thread_id=thread_id,
        direction=direction,
        kind=kind,
        subject=subject,
        body=body,
        status=status,
    )
    db.add(message)
    await db.flush()
    return message


async def list_outreach_messages(db: AsyncSession, *, thread_id: str) -> list[OutreachMessage]:
    result = await db.execute(
        select(OutreachMessage).where(OutreachMessage.thread_id == thread_id).order_by(OutreachMessage.created_at)
    )
    return list(result.scalars().all())


async def get_outreach_message(db: AsyncSession, *, thread_id: str, message_id: str) -> Optional[OutreachMessage]:
    result = await db.execute(
        select(OutreachMessage).where(OutreachMessage.id == message_id, OutreachMessage.thread_id == thread_id)
    )
    return result.scalar_one_or_none()


async def approve_outreach_message(db: AsyncSession, *, message_id: str) -> OutreachMessage:
    """Raises ValueError (caller maps to 409) — a direct creator action from
    a button click needs an invalid transition to surface, not vanish (same
    convention as app/domain/content/service.py::mark_content_stage)."""
    message = await db.get(OutreachMessage, message_id)
    if message is None:
        raise ValueError("Outreach message not found.")
    if message.status not in MESSAGE_APPROVABLE_FROM:
        raise ValueError(f"Cannot approve from status {message.status!r} (expected one of {MESSAGE_APPROVABLE_FROM}).")
    message.status = "approved"
    if message.kind == "initial_pitch":
        thread = await db.get(OutreachThread, message.thread_id)
        if thread is not None and thread.status == "drafting":
            thread.status = "approved"
    await db.flush()
    return message


async def mark_outreach_message_sent(db: AsyncSession, *, message_id: str) -> OutreachMessage:
    """The only path a message can reach 'sent' — requires 'approved' first
    (CLAUDE.md §70's human-in-the-loop gate), and is only ever called from
    an explicit creator action, never automatically."""
    message = await db.get(OutreachMessage, message_id)
    if message is None:
        raise ValueError("Outreach message not found.")
    if message.status not in MESSAGE_SENDABLE_FROM:
        raise ValueError(f"Cannot mark sent from status {message.status!r} (expected one of {MESSAGE_SENDABLE_FROM}).")
    message.status = "sent"
    message.sent_at = datetime.now(timezone.utc)
    if message.kind == "initial_pitch":
        thread = await db.get(OutreachThread, message.thread_id)
        if thread is not None and thread.status == "approved":
            thread.status = "sent"
    await db.flush()
    return message


# --- Response extraction + creator decision (CLAUDE.md §66, Part II Phase 7) -
# The agent (classify_response, app/agent_service/agents/outreach.py) only
# ever produces a read-only extraction attached to the inbound message it
# belongs to. record_creator_decision is the ONLY function in this entire
# module — in this entire codebase — allowed to write
# OutreachThread.outcome/creator_decision. It is only ever called from an
# explicit creator action (a route handling a decision button click), never
# from an agent (CLAUDE.md §66).

CREATOR_DECISIONS = ("accept", "negotiate", "decline", "need_more_info", "archive")
# Each decision's effect on the thread's pipeline stage and outcome. A
# decision that isn't a real resolution yet (negotiate/need_more_info) only
# records the creator's stated intent — it doesn't close the thread out.
_DECISION_EFFECTS: dict[str, tuple[Optional[str], Optional[str]]] = {
    "accept": ("won", "deal_confirmed"),
    "decline": ("lost", "declined_by_creator"),
    "negotiate": (None, None),
    "need_more_info": (None, None),
    "archive": ("archived", "archived_by_creator"),
}


async def record_brand_reply(
    db: AsyncSession, *, thread_id: str, body: str, subject: Optional[str] = None
) -> OutreachMessage:
    """Recording that a reply happened is plain data entry, not
    intelligence — it must succeed regardless of whether extraction
    (a separate step, see apply_extracted_data) later succeeds or is
    skipped in stub mode, so the creator's evidence is never lost to an
    agent hiccup (CLAUDE.md §43)."""
    message = await add_outreach_message(
        db, thread_id=thread_id, direction="inbound", kind="brand_reply", subject=subject, body=body, status=None
    )
    thread = await db.get(OutreachThread, thread_id)
    if thread is not None and thread.status == "sent":
        thread.status = "replied"
    await db.flush()
    return message


async def apply_extracted_data(db: AsyncSession, *, message_id: str, extracted_data: dict) -> OutreachMessage:
    message = await db.get(OutreachMessage, message_id)
    if message is None:
        raise ValueError("Outreach message not found.")
    message.extracted_data = extracted_data
    await db.flush()
    return message


async def record_creator_decision(
    db: AsyncSession, *, thread_id: str, decision: str, note: Optional[str] = None
) -> OutreachThread:
    """Raises ValueError (caller maps to 409/400) on an unrecognized
    decision, or on a thread that's already resolved — same "surface,
    don't vanish" convention as the message status gates above. Once a
    thread has a terminal outcome (won/lost/archived), it can never be
    re-decided: a commercial-category StrategicLearning's evidence_ids and
    statement are derived from resolved outcomes (Part II §72), and
    letting a resolved thread flip outcome later would silently invalidate
    a learning's already-persisted evidence without any corresponding
    correction — CLAUDE.md §16's evidence-traceability guarantee would
    otherwise quietly break. A still-open decision (negotiate/
    need_more_info) can be updated freely, since neither sets an outcome."""
    if decision not in CREATOR_DECISIONS:
        raise ValueError(f"Unrecognized decision {decision!r} (expected one of {CREATOR_DECISIONS}).")
    thread = await db.get(OutreachThread, thread_id)
    if thread is None:
        raise ValueError("Outreach thread not found.")
    if thread.outcome is not None:
        raise ValueError(f"This thread is already resolved (outcome={thread.outcome!r}) and cannot be re-decided.")

    new_status, outcome = _DECISION_EFFECTS[decision]
    thread.creator_decision = decision
    thread.creator_decision_note = note
    thread.decided_at = datetime.now(timezone.utc)
    if new_status is not None:
        thread.status = new_status
        thread.outcome = outcome
    await db.flush()
    return thread
