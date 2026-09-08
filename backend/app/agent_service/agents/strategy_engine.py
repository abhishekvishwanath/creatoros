"""Strategy Engine Agent (CLAUDE.md §21: content-as-portfolio).

Turns a creator's approved/saved opportunities into a balanced weekly
portfolio: not "publish whatever scored highest seven times," but a
deliberate mix of portfolio roles (reach, authority, community, story,
conversion, experimental) scheduled across the week. Every item must be
grounded in a real opportunity id from what was given (same hallucination
guard as the Opportunity Engine, CLAUDE.md §3.4) — a role/day assignment for
an opportunity the model invented is worse than leaving that day open.

No honest rule-based fallback exists (portfolio balance needs real judgment
about the creator's goals and mix), so — like voice, pillars, and
opportunity scoring — this is skipped outright in stub mode.
"""

from app.agent_service.agents.base import BaseAgent
from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.schemas.creator import CreatorStateSnapshot

PORTFOLIO_ROLES = {"reach", "authority", "community", "story", "conversion", "experimental"}

STRATEGY_SYSTEM_PROMPT = """You are the Strategy Engine inside a Creator \
Intelligence OS. You will be given a creator's positioning, active goals, \
existing content pillars, and a list of opportunities they've already \
approved or saved — each labeled with an opportunity id.

Build a one-week content portfolio from these opportunities. Content-as-
portfolio means deliberately mixing roles rather than only picking whatever \
scored highest:
- reach: designed to bring in new audience
- authority: demonstrates expertise, builds trust
- community: invites conversation/participation
- story: personal, narrative, builds connection
- conversion: pushes toward a goal (sale, signup, etc.)
- experimental: tests a new angle/format with unclear payoff

Select up to 7 of the given opportunities (fewer is fine — never invent one \
that isn't in the list), assign each a day_of_week integer (0=Monday ... \
6=Sunday, at most one opportunity per day), and a portfolio_role from \
exactly the six listed above. Favor a mix of roles over repeating the same \
one, and weight selection toward the creator's stated goals where relevant.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"summary": string, "items": [{"opportunity_id": string, "day_of_week": number, \
"portfolio_role": string}]}
"""


class StrategyEngineAgent(BaseAgent):
    name = "strategy_engine"
    allowed_tools: list[str] = []

    async def run(
        self,
        context: CreatorStateSnapshot,
        model_router: ModelRouter,
        available_opportunities: list[dict] | None = None,
    ) -> AgentOutput:
        available_opportunities = available_opportunities or []
        if not available_opportunities:
            return AgentOutput(
                status="success",
                summary="Strategy: skipped, no approved or saved opportunities are available yet.",
                confidence=0.0,
                inputs_used=[],
                evidence_ids=[],
                proposed_state_changes=[],
                next_action="Approve or save opportunities in Opportunities before generating a strategy.",
                warnings=["No approved or saved opportunities available."],
            )

        valid_ids = {o["id"] for o in available_opportunities}
        user_parts = []
        creator = context.creator
        if context.positioning and context.positioning.positioning_statement:
            user_parts.append(f"Positioning: {context.positioning.positioning_statement}")
        elif creator.niche:
            user_parts.append(f"Niche: {creator.niche}")
        if context.active_goals:
            goal_lines = ", ".join(g.description or g.goal_type for g in context.active_goals)
            user_parts.append(f"Active goals: {goal_lines}")
        if context.content_pillars:
            names = ", ".join(p["name"] for p in context.content_pillars)
            user_parts.append(f"Existing content pillars: {names}")

        opp_lines = "\n".join(
            f"[{o['id']}] topic={o.get('topic')!r} subtopic={o.get('subtopic')!r} "
            f"format={o.get('format')!r} score={o.get('score')}"
            for o in available_opportunities
        )
        user_parts.append(f"Available opportunities:\n{opp_lines}")

        response, failure = await self._complete_safely(
            model_router,
            tier=ModelTier.STANDARD,
            system=STRATEGY_SYSTEM_PROMPT,
            user="\n\n".join(user_parts),
            label="Strategy",
            inputs_used=["available_opportunities", "positioning", "active_goals", "content_pillars"],
            evidence_ids=list(valid_ids),
        )
        if failure:
            return failure

        if response.stub:
            return AgentOutput(
                status="success",
                summary="Strategy: skipped (no model provider configured, and portfolio balancing has no honest rule-based fallback).",
                confidence=0.0,
                inputs_used=["available_opportunities"],
                evidence_ids=list(valid_ids),
                warnings=[
                    "No ANTHROPIC_API_KEY or GROQ_API_KEY configured — building a balanced portfolio needs a "
                    "real model read of the opportunities and goals, so it was skipped rather than guessed."
                ],
            )

        try:
            data = self._parse_json(response.text, required_key="items")
        except ValueError as exc:
            return AgentOutput(
                status="failed",
                summary="Strategy: model response could not be parsed as the expected JSON shape.",
                confidence=0.0,
                inputs_used=["available_opportunities"],
                evidence_ids=list(valid_ids),
                warnings=[str(exc)],
            )

        raw_items = data.get("items", [])
        # Ground every item: a made-up opportunity id, an out-of-range day,
        # or a role outside the fixed six is dropped rather than coerced —
        # a wrong-but-present value would silently corrupt the portfolio
        # view, whereas a missing day is an honest, visible gap.
        grounded_items = [
            item
            for item in raw_items
            if item.get("opportunity_id") in valid_ids
            and isinstance(item.get("day_of_week"), int)
            and 0 <= item["day_of_week"] <= 6
            and item.get("portfolio_role") in PORTFOLIO_ROLES
        ]

        # The prompt asks for at most one opportunity per day, but nothing
        # stops the model from double-booking a day anyway — silently
        # inserting both would let the second item's opportunity get marked
        # "used" on activation while never appearing in the (day-keyed)
        # calendar view. Keep the first occurrence per day, drop the rest.
        valid_items = []
        seen_days: set[int] = set()
        for item in grounded_items:
            if item["day_of_week"] in seen_days:
                continue
            seen_days.add(item["day_of_week"])
            valid_items.append(item)

        used_ids = {item["opportunity_id"] for item in valid_items}
        coverage = len(used_ids) / len(valid_ids) if valid_ids else 0.0
        confidence = round(min(0.3 + 0.3 * coverage, 0.6), 2)

        dropped = len(raw_items) - len(valid_items)
        warnings = [f"Dropped {dropped} proposed item(s) with an invalid opportunity id, day, role, or day collision."] if dropped else []

        return AgentOutput(
            status="success",
            summary=data.get("summary", f"Built a {len(valid_items)}-item weekly portfolio.") if valid_items else "Strategy: no valid items survived grounding.",
            confidence=confidence,
            inputs_used=["available_opportunities", "positioning", "active_goals", "content_pillars"],
            evidence_ids=list(used_ids),
            proposed_state_changes=[
                {
                    "type": "strategy_upsert",
                    "data": {"summary": data.get("summary", ""), "items": valid_items},
                    "confidence": confidence,
                    "evidence_ids": list(used_ids),
                }
            ]
            if valid_items
            else [],
            next_action="Review and activate the proposed strategy." if valid_items else None,
            warnings=warnings,
        )
