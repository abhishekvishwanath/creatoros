"""Brand Intelligence Agent (CLAUDE.md §68-71, Part II Phase 3).

Scores a specific brand's fit for this creator. Folds in what the original
commercial spec calls "Brand Discovery," "Brand Intelligence/Qualification,"
and "Contact Discovery" into one agent (CLAUDE.md §20's own warning against
unnecessary agent proliferation) — without a live search/enrichment API,
those three reduce to: reason over what's already known/typed in, and
suggest role titles worth looking for, rather than three genuinely distinct
reasoning jobs.

Only scores dimensions this system actually has a groundable evidence
source for (CLAUDE.md §71/§20 — no opaque, ungrounded numbers):
audience_fit, creator_fit, product_content_fit, timing_signal, and
historical_category_fit (the last reads commercial-category
StrategicLearning rows once Part II Phase 8 exists to produce them; scored
neutral 0.5 with no evidence yet). `contactability` is always computed in
code (app/agent_service/context/builder.py::compute_contactability), never
proposed by the model. "Budget plausibility" and "relationship strength"
from the original spec's suggested dimensions are deliberately not scored
at all — there's no data source for the former, and the latter is only
meaningful after outreach history exists.
"""

from app.agent_service.agents.base import BaseAgent
from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.domain.commercial.service import BRAND_OPPORTUNITY_SCORE_DIMENSIONS
from app.schemas.creator import CreatorStateSnapshot

BRAND_SCORE_METRICS = BRAND_OPPORTUNITY_SCORE_DIMENSIONS

BRAND_INTELLIGENCE_SYSTEM_PROMPT = """You are the Brand Intelligence Agent \
inside a Creator Intelligence OS. You will be given a creator's positioning, \
audience, content pillars/recent content, commercial DNA (ideal/prohibited \
sponsor categories, goals), any commercial-category learnings from past \
sponsorships, and one specific brand with whatever signals the creator has \
observed about it — each signal labeled with an id.

Score how good a commercial fit this ONE brand is for this ONE creator, on \
each of these dimensions from 0.0 to 1.0, grounded only in what's given:
- audience_fit: does this creator's audience plausibly want/use this brand's product?
- creator_fit: does this brand fit the creator's positioning, pillars, and stated commercial preferences?
- product_content_fit: could the creator's existing content style/format credibly showcase this brand?
- timing_signal: do the GIVEN brand signals suggest good timing (e.g. a recent launch, a creator program)? If no signals are given, score exactly 0.5 (no evidence either way) — never invent a reason.
- historical_category_fit: if given any commercial-category learnings relevant to this brand's category, use them; otherwise score exactly 0.5.

Also write 2-4 sentences of `reasons` explaining the scores in plain \
language, citing only the given signal ids as evidence_signal_ids. If the \
brand's category conflicts with the creator's stated prohibited categories \
(you will be told explicitly if it does), say so plainly in reasons rather \
than silently scoring around it — the creator decides what to do with that, \
you just surface it.

Also suggest up to 3 contact_role titles (e.g. "Creator Partnerships \
Manager", "Influencer Marketing Lead") worth looking for at this brand, \
based on its size/category — generic role titles only, never a specific \
person's name. Skip any role already in the given existing_contact_roles.

Do not invent facts about the brand beyond what's given (no specific recent \
events, no financials, no named executives) — general category/positioning \
reasoning is fine, but never state a specific brand event as fact unless a \
given signal supports it.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"score_components": {"audience_fit": number, "creator_fit": number, \
"product_content_fit": number, "timing_signal": number, "historical_category_fit": number}, \
"reasons": string, "evidence_signal_ids": string[], "contact_roles": string[]}
"""


class BrandIntelligenceAgent(BaseAgent):
    name = "brand_intelligence"
    allowed_tools: list[str] = []

    async def run(
        self,
        context: CreatorStateSnapshot,
        model_router: ModelRouter,
        brand: dict | None = None,
        signals: list[dict] | None = None,
        existing_contact_roles: list[str] | None = None,
        contactability: float = 0.0,
    ) -> AgentOutput:
        brand = brand or {}
        signals = signals or []
        existing_contact_roles = existing_contact_roles or []
        valid_signal_ids = {s["id"] for s in signals}

        user_parts = [f"Brand: name={brand.get('name')!r} category={brand.get('category')!r}"]
        if brand.get("description"):
            user_parts.append(f"Description: {brand['description']}")
        if brand.get("positioning"):
            user_parts.append(f"Positioning: {brand['positioning']}")

        if signals:
            signal_lines = "\n".join(f"[{s['id']}] ({s.get('signal_type')}) {s.get('summary')}" for s in signals)
            user_parts.append(f"Brand signals:\n{signal_lines}")
        else:
            user_parts.append("Brand signals: none observed yet.")

        if context.positioning and context.positioning.positioning_statement:
            user_parts.append(f"Creator positioning: {context.positioning.positioning_statement}")
        if context.content_pillars:
            names = ", ".join(p["name"] for p in context.content_pillars)
            user_parts.append(f"Content pillars: {names}")
        if context.audience and context.audience.knowledge_level:
            user_parts.append(f"Audience: {context.audience.knowledge_level}")

        commercial = context.commercial_profile
        prohibited_conflict = False
        if commercial:
            if commercial.ideal_sponsor_categories:
                user_parts.append(f"Ideal sponsor categories: {', '.join(commercial.ideal_sponsor_categories)}")
            if commercial.prohibited_categories:
                user_parts.append(f"Prohibited categories: {', '.join(commercial.prohibited_categories)}")
                brand_category = (brand.get("category") or "").lower()
                prohibited_conflict = any(
                    p.lower() in brand_category or brand_category in p.lower()
                    for p in commercial.prohibited_categories
                    if brand_category and p
                )
                if prohibited_conflict:
                    user_parts.append(
                        "NOTE: this brand's category appears to conflict with a stated prohibited category — "
                        "say so explicitly in reasons."
                    )
            if commercial.sponsorship_goals:
                user_parts.append(f"Sponsorship goals: {commercial.sponsorship_goals}")

        # strategic_learnings' summary shape (CreatorStateSnapshot) doesn't
        # carry the DB row's category prefix, so this hands over every
        # active learning and trusts the model to judge relevance from the
        # brand's own category vs. each learning's statement text — the
        # same way a human reading both would. Until Part II Phase 8 exists
        # to produce any commercial-category learnings, this list is simply
        # whatever content-performance learnings already exist (or empty),
        # and the prompt instruction above (score exactly 0.5 with nothing
        # relevant) still applies.
        if context.strategic_learnings:
            learning_lines = "\n".join(f"- {l['statement']}" for l in context.strategic_learnings)
            user_parts.append(f"Strategic learnings (content and commercial, if any apply to this category):\n{learning_lines}")

        if existing_contact_roles:
            user_parts.append(f"Existing contact roles already on file: {', '.join(existing_contact_roles)}")

        response, failure = await self._complete_safely(
            model_router,
            tier=ModelTier.STANDARD,
            system=BRAND_INTELLIGENCE_SYSTEM_PROMPT,
            user="\n\n".join(user_parts),
            label="Brand intelligence",
            inputs_used=["brand", "signals", "positioning", "commercial_profile", "strategic_learnings"],
            evidence_ids=list(valid_signal_ids),
        )
        if failure:
            return failure

        if response.stub:
            return AgentOutput(
                status="success",
                summary="Brand scoring: skipped (no model provider configured, and scoring has no honest rule-based fallback).",
                confidence=0.0,
                inputs_used=["brand"],
                evidence_ids=list(valid_signal_ids),
                warnings=[
                    "No ANTHROPIC_API_KEY or GROQ_API_KEY configured — brand fit needs real judgment, "
                    "so it was skipped rather than guessed."
                ],
            )

        try:
            data = self._parse_json(response.text, required_key="score_components")
        except ValueError as exc:
            return AgentOutput(
                status="failed",
                summary="Brand scoring: model response could not be parsed as the expected JSON shape.",
                confidence=0.0,
                inputs_used=["brand"],
                evidence_ids=list(valid_signal_ids),
                warnings=[str(exc)],
            )

        raw_components = data.get("score_components") or {}
        # Grounding: an out-of-range or missing dimension is dropped, not
        # coerced — a wrong-but-present score would silently corrupt the
        # combined average computed downstream in code.
        components = {
            metric: raw_components[metric]
            for metric in BRAND_SCORE_METRICS
            if isinstance(raw_components.get(metric), (int, float)) and 0.0 <= raw_components[metric] <= 1.0
        }
        cited_ids = [sid for sid in (data.get("evidence_signal_ids") or []) if sid in valid_signal_ids]
        contact_roles = [r for r in (data.get("contact_roles") or []) if isinstance(r, str)][:3]

        if not components:
            return AgentOutput(
                status="failed",
                summary="Brand scoring: model returned no usable score components.",
                confidence=0.0,
                inputs_used=["brand"],
                evidence_ids=cited_ids,
                warnings=["No score_components survived grounding (missing, non-numeric, or out of 0-1 range)."],
            )

        # Same evidence-coverage-based confidence formula as every other
        # grounded-synthesis agent (strategy/creator/audience/opportunity —
        # BaseAgent._coverage_confidence), not a model self-reported label —
        # a brand with no observed signals shouldn't be able to talk itself
        # into "high confidence" just by picking that word.
        coverage = len(cited_ids) / len(valid_signal_ids) if valid_signal_ids else 0.0
        confidence = self._coverage_confidence(coverage)

        return AgentOutput(
            status="success",
            summary=f"Scored {brand.get('name')!r} across {len(components)} dimensions.",
            confidence=confidence,
            inputs_used=["brand", "signals", "positioning", "commercial_profile", "strategic_learnings"],
            evidence_ids=cited_ids,
            proposed_state_changes=[
                {
                    "type": "brand_opportunity_score",
                    "data": {
                        "score_components": components,
                        "reasons": data.get("reasons", ""),
                        "evidence_signal_ids": cited_ids,
                        "suggested_contact_roles": contact_roles,
                        "prohibited_conflict": prohibited_conflict,
                    },
                    "confidence": confidence,
                    "evidence_ids": cited_ids,
                }
            ],
            warnings=["This brand's category appears to conflict with a stated prohibited category."]
            if prohibited_conflict
            else [],
        )
