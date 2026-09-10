"""Campaign Intelligence Agent (CLAUDE.md commercial spec §9, Part II Phase 5).

Turns a scored BrandOpportunity into a complete campaign brief — the
commercial-loop analog of ContentArchitectAgent turning an opportunity into a
content brief (app/agent_service/agents/content_architect.py), same
evidence-grounding rules, same "skip outright in stub mode" posture (pitch
strategy needs real creative/commercial reasoning, and there is no honest
rule-based fallback for it).

`suggested_deliverables` is explicitly a proposal the creator can accept,
edit, or discard — never a commitment. The agent only ever produces a draft;
CLAUDE.md §66 is the hard constraint that nothing downstream of this (an
outreach thread, a message) may be sent or treated as agreed without an
explicit creator action.
"""

from app.agent_service.agents.base import BaseAgent
from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.schemas.creator import CreatorStateSnapshot

CAMPAIGN_INTELLIGENCE_SYSTEM_PROMPT = """You are the Campaign Intelligence \
Agent inside a Creator Intelligence OS. You will be given a creator's \
positioning, voice, commercial preferences (ideal sponsor categories, \
sponsorship goals), one specific brand that has already been scored as a \
commercial fit (with the score's own reasons/components), and whatever \
signals the creator has observed about that brand — each signal labeled \
with an id.

Produce a campaign brief for a potential sponsorship pitch to this ONE \
brand: a working hypothesis for what this partnership could achieve, a \
concrete campaign concept, the content format it would take, why THIS \
brand specifically fits (grounded in its positioning/category and the \
given fit reasons), why NOW (grounded only in given signals — if none are \
given, say the timing case is speculative rather than inventing one), a \
suggested call-to-action for the pitch itself, up to 5 suggested \
deliverables framed as a STARTING PROPOSAL the brand and creator would \
still negotiate (never phrase these as already agreed), a one-sentence \
pitch angle, and up to 4 personalization facts — concrete, specific details \
this creator could reference in outreach to prove they did their homework, \
drawn only from the given brand/signal information, never invented.

Do not invent facts about the brand beyond what's given (no specific recent \
events, deals, executives, or financials unless a given signal supports \
them) — general category/positioning reasoning is fine, stating something \
as a specific fact about this brand is not, unless grounded.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"objective_hypothesis": string, "campaign_concept": string, \
"content_format": string, "why_this_brand": string, "why_now": string, \
"suggested_cta": string, "suggested_deliverables": string[], \
"pitch_angle": string, "personalization_facts": string[], \
"evidence_signal_ids": string[]}
"""


class CampaignIntelligenceAgent(BaseAgent):
    name = "campaign_intelligence"
    allowed_tools: list[str] = []

    async def run(
        self,
        context: CreatorStateSnapshot,
        model_router: ModelRouter,
        brand: dict | None = None,
        signals: list[dict] | None = None,
        opportunity: dict | None = None,
    ) -> AgentOutput:
        brand = brand or {}
        signals = signals or []
        opportunity = opportunity or {}
        valid_signal_ids = {s["id"] for s in signals}

        user_parts = [f"Brand: name={brand.get('name')!r} category={brand.get('category')!r}"]
        if brand.get("description"):
            user_parts.append(f"Description: {brand['description']}")
        if brand.get("positioning"):
            user_parts.append(f"Positioning: {brand['positioning']}")

        if opportunity.get("reasons"):
            user_parts.append(
                f"Fit score: {opportunity.get('score')} (components: {opportunity.get('score_components')}). "
                f"Reasons: {opportunity['reasons']}"
            )

        if signals:
            signal_lines = "\n".join(f"[{s['id']}] ({s.get('signal_type')}) {s.get('summary')}" for s in signals)
            user_parts.append(f"Brand signals (the only source for 'why now' and personalization facts):\n{signal_lines}")
        else:
            user_parts.append("Brand signals: none observed yet — timing/personalization must stay speculative.")

        if context.positioning and context.positioning.positioning_statement:
            user_parts.append(f"Creator positioning: {context.positioning.positioning_statement}")
        if context.voice and context.voice.tone:
            user_parts.append(f"Creator voice: tone={context.voice.tone}, personality={context.voice.personality}")

        commercial = context.commercial_profile
        if commercial:
            if commercial.ideal_sponsor_categories:
                user_parts.append(f"Ideal sponsor categories: {', '.join(commercial.ideal_sponsor_categories)}")
            if commercial.sponsorship_goals:
                user_parts.append(f"Sponsorship goals: {commercial.sponsorship_goals}")
            if commercial.preferred_deal_formats:
                user_parts.append(f"Preferred deal formats: {', '.join(commercial.preferred_deal_formats)}")

        response, failure = await self._complete_safely(
            model_router,
            tier=ModelTier.STANDARD,
            system=CAMPAIGN_INTELLIGENCE_SYSTEM_PROMPT,
            user="\n\n".join(user_parts),
            label="Campaign brief",
            inputs_used=["brand", "signals", "opportunity", "positioning", "voice", "commercial_profile"],
            evidence_ids=list(valid_signal_ids),
            # A ~10-field JSON with several string-array fields — same
            # headroom reasoning as ContentArchitectAgent's brief.
            max_tokens=1600,
        )
        if failure:
            return failure

        if response.stub:
            return AgentOutput(
                status="success",
                summary="Campaign brief: skipped (no model provider configured, and pitch strategy has no honest rule-based fallback).",
                confidence=0.0,
                inputs_used=["brand"],
                evidence_ids=list(valid_signal_ids),
                warnings=[
                    "No ANTHROPIC_API_KEY or GROQ_API_KEY configured — a campaign brief needs real "
                    "creative/commercial reasoning, so it was skipped rather than guessed."
                ],
            )

        try:
            data = self._parse_json(response.text, required_key="campaign_concept")
        except ValueError as exc:
            return AgentOutput(
                status="failed",
                summary="Campaign brief: model response could not be parsed as the expected JSON shape.",
                confidence=0.0,
                inputs_used=["brand"],
                evidence_ids=list(valid_signal_ids),
                warnings=[str(exc)],
            )

        cited_ids = [sid for sid in (data.get("evidence_signal_ids") or []) if sid in valid_signal_ids]
        deliverables = [d for d in (data.get("suggested_deliverables") or []) if isinstance(d, str)][:5]
        personalization_facts = [f for f in (data.get("personalization_facts") or []) if isinstance(f, str)][:4]

        coverage = len(cited_ids) / len(valid_signal_ids) if valid_signal_ids else 0.0
        confidence = self._coverage_confidence(coverage)

        return AgentOutput(
            status="success",
            summary=f"Drafted a campaign brief for {brand.get('name')!r}.",
            confidence=confidence,
            inputs_used=["brand", "signals", "opportunity", "positioning", "voice", "commercial_profile"],
            evidence_ids=cited_ids,
            proposed_state_changes=[
                {
                    "type": "campaign_brief_upsert",
                    "data": {
                        "objective_hypothesis": data.get("objective_hypothesis", ""),
                        "campaign_concept": data.get("campaign_concept", ""),
                        "content_format": data.get("content_format", ""),
                        "why_this_brand": data.get("why_this_brand", ""),
                        "why_now": data.get("why_now", ""),
                        "suggested_cta": data.get("suggested_cta", ""),
                        "suggested_deliverables": deliverables,
                        "pitch_angle": data.get("pitch_angle", ""),
                        "personalization_facts": personalization_facts,
                        "evidence_signal_ids": cited_ids,
                    },
                    "confidence": confidence,
                    "evidence_ids": cited_ids,
                }
            ],
            next_action="Draft outreach from this brief.",
            warnings=[],
        )
