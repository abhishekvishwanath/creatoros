"""Opportunity Engine Agent (CLAUDE.md §20).

Turns ingested research signals into scored, evidence-linked content
opportunities. Every opportunity must trace back to the specific signal(s)
that justify it (CLAUDE.md §3.4, §16) — the agent is required to cite which
input signal ids support each proposal, and score_components are always kept
broken out rather than collapsed into a single number the model made up
(CLAUDE.md §20 last line): the agent supplies component scores, but the
*combined* score is computed in code (app/domain/research/service.py) so an
opaque model-invented aggregate never reaches the database.

No honest rule-based fallback exists for this job (spotting a genuine
opportunity from raw signals needs real reasoning), so — like voice and
pillar inference — it is skipped outright in stub mode rather than guessed.
"""

from app.agent_service.agents.base import BaseAgent
from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.schemas.creator import CreatorStateSnapshot

OPPORTUNITY_SYSTEM_PROMPT = """You are the Opportunity Engine inside a Creator \
Intelligence OS. You will be given a creator's positioning, their existing \
content pillars, their active goals, and a list of research signals they (or \
their team) observed elsewhere — each labeled with a signal id.

Propose 3 to 6 concrete content opportunities grounded in these signals. Do \
not propose an opportunity with no signal behind it — every opportunity must \
cite at least one signal id from the list given. Do not invent engagement \
numbers, competitor names, or facts not present in the signals.

For each opportunity, score these components from 0.0 to 1.0 based only on \
what the given context supports:
- audience_fit: how well it fits what this creator's audience wants
- creator_fit: how well it fits this creator's positioning/pillars
- demand: how much signal evidence suggests real interest in this topic
- novelty: how fresh this angle is versus what's already saturated
- evidence: how strong/direct the cited signal(s) actually are

Also estimate competition_level, saturation_estimate, and
production_complexity as one of "low", "medium", "high", and a
recommended_time_window as a short free-text phrase (e.g. "this week").
If a proposed opportunity clearly matches one of the creator's existing
content pillar names, include that exact name as content_pillar_name.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"opportunities": [{"topic": string, "subtopic": string, "angle": string, \
"format": string, "content_pillar_name": string | null, \
"score_components": {"audience_fit": number, "creator_fit": number, \
"demand": number, "novelty": number, "evidence": number}, \
"competition_level": string, "saturation_estimate": string, \
"production_complexity": string, "recommended_time_window": string, \
"evidence_signal_ids": string[]}]}
"""


class OpportunityEngineAgent(BaseAgent):
    name = "opportunity_engine"
    allowed_tools: list[str] = []

    async def run(
        self,
        context: CreatorStateSnapshot,
        model_router: ModelRouter,
        research_signals: list[dict] | None = None,
    ) -> AgentOutput:
        research_signals = research_signals or []
        if not research_signals:
            return AgentOutput(
                status="success",
                summary="Opportunities: skipped, no research signals have been ingested yet.",
                confidence=0.0,
                inputs_used=[],
                evidence_ids=[],
                proposed_state_changes=[],
                next_action="Ingest research signals (competitor posts, trends, audience questions) to generate opportunities.",
                warnings=["No research signals available."],
            )

        all_signal_ids = [s["id"] for s in research_signals]
        user_parts = []
        creator = context.creator
        if context.positioning and context.positioning.positioning_statement:
            user_parts.append(f"Positioning: {context.positioning.positioning_statement}")
        elif creator.niche:
            user_parts.append(f"Niche: {creator.niche}")
        if context.content_pillars:
            names = ", ".join(p["name"] for p in context.content_pillars)
            user_parts.append(f"Existing content pillars: {names}")
        if context.active_goals:
            goal_lines = ", ".join(g.description or g.goal_type for g in context.active_goals)
            user_parts.append(f"Active goals: {goal_lines}")

        signal_lines = "\n".join(
            f"[{s['id']}] topic={s.get('topic')!r} subtopic={s.get('subtopic')!r} "
            f"format={s.get('format')!r} platform={s.get('platform')!r}: {s.get('summary', '')}"
            for s in research_signals
        )
        user_parts.append(f"Research signals:\n{signal_lines}")

        response, failure = await self._complete_safely(
            model_router,
            tier=ModelTier.STANDARD,
            system=OPPORTUNITY_SYSTEM_PROMPT,
            user="\n\n".join(user_parts),
            label="Opportunities",
            inputs_used=["research_signals", "positioning", "content_pillars"],
            evidence_ids=all_signal_ids,
        )
        if failure:
            return failure

        if response.stub:
            return AgentOutput(
                status="success",
                summary="Opportunities: skipped (no model provider configured, and opportunity scoring has no honest rule-based fallback).",
                confidence=0.0,
                inputs_used=["research_signals"],
                evidence_ids=all_signal_ids,
                warnings=[
                    "No ANTHROPIC_API_KEY or GROQ_API_KEY configured — opportunity scoring needs a "
                    "real model read of the signals, so it was skipped rather than guessed."
                ],
            )

        try:
            data = self._parse_json(response.text, required_key="opportunities")
        except ValueError as exc:
            return AgentOutput(
                status="failed",
                summary="Opportunities: model response could not be parsed as the expected JSON shape.",
                confidence=0.0,
                inputs_used=["research_signals"],
                evidence_ids=all_signal_ids,
                warnings=[str(exc)],
            )

        opportunities = data.get("opportunities", [])
        valid_ids = set(all_signal_ids)
        # Drop any opportunity that cites no real signal id, or only ids the
        # model made up — an ungrounded proposal is worse than none. Any
        # *surviving* opportunity also has its evidence_signal_ids filtered
        # down to real ids only: a hallucinated id mixed in with a real one
        # would otherwise reach apply_opportunities and violate the
        # research_signals foreign key on write.
        grounded = []
        for o in opportunities:
            real_ids = [sid for sid in o.get("evidence_signal_ids", []) if sid in valid_ids]
            if real_ids:
                o["evidence_signal_ids"] = real_ids
                grounded.append(o)

        cited_ids = {sid for o in grounded for sid in o["evidence_signal_ids"]}
        coverage = len(cited_ids) / len(valid_ids) if valid_ids else 0.0
        confidence = round(min(0.3 + 0.3 * coverage, 0.6), 2)
        for o in grounded:
            o["confidence"] = confidence

        return AgentOutput(
            status="success",
            summary=f"Proposed {len(grounded)} opportunity(ies) from {len(research_signals)} research signal(s).",
            confidence=confidence,
            inputs_used=["research_signals", "positioning", "content_pillars"],
            evidence_ids=list(cited_ids),
            proposed_state_changes=[
                {
                    "type": "opportunities_upsert",
                    "data": {"opportunities": grounded},
                    "confidence": confidence,
                    "evidence_ids": list(cited_ids),
                }
            ]
            if grounded
            else [],
            next_action="Review and approve/reject the proposed opportunities." if grounded else None,
            warnings=[] if len(grounded) == len(opportunities) else [
                f"Dropped {len(opportunities) - len(grounded)} proposed opportunity(ies) that cited no real signal id."
            ],
        )
