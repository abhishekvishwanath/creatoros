"""Creator Intelligence Agent (CLAUDE.md §11.1).

At this stage the only inputs available are what the creator typed at
onboarding (name, niche, business model, goals) — there's no ingested content
yet (that's Phase 5+: content ingestion, then this agent's real job of
inferring voice/positioning from a content history). So this first version
does the honest thing for a cold start: synthesizes a *tentative* positioning
statement from onboarding fields alone, and marks it explicitly low-confidence
so the UI and any downstream agent knows not to treat it as settled (CLAUDE.md
§5.3: never let a thin signal become a permanent "truth").
"""

import json
import re

from app.agent_service.agents.base import BaseAgent
from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.schemas.creator import CreatorStateSnapshot

SYSTEM_PROMPT = """You are the Creator Intelligence Agent inside a Creator \
Intelligence OS. Your job is to synthesize a short, specific positioning \
statement and a list of likely areas of expertise for a content creator, \
based only on the limited onboarding information given to you.

Do not invent specific facts, credentials, achievements, or audience size \
that were not given to you. Write the positioning statement as a hypothesis \
to be refined once real content history is analyzed, not as an established \
fact.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"positioning_statement": string, "expertise": string[], "bio": string}
"""


class CreatorIntelligenceAgent(BaseAgent):
    name = "creator_intelligence"
    allowed_tools: list[str] = []

    async def run(self, context: CreatorStateSnapshot, model_router: ModelRouter) -> AgentOutput:
        creator = context.creator
        inputs_used = ["onboarding.name", "onboarding.niche"]
        user_parts = [f"Name: {creator.name}"]
        if creator.niche:
            user_parts.append(f"Niche: {creator.niche}")
        if creator.sub_niche:
            user_parts.append(f"Sub-niche: {creator.sub_niche}")
            inputs_used.append("onboarding.sub_niche")
        if creator.business_model:
            user_parts.append(f"Business model: {creator.business_model}")
            inputs_used.append("onboarding.business_model")
        if creator.monetization_model:
            user_parts.append(f"Monetization: {creator.monetization_model}")
            inputs_used.append("onboarding.monetization_model")
        if context.active_goals:
            goal_lines = ", ".join(g.description or g.goal_type for g in context.active_goals)
            user_parts.append(f"Active goals: {goal_lines}")
            inputs_used.append("creator_goals")

        response = await model_router.complete(
            tier=ModelTier.STANDARD,
            system=SYSTEM_PROMPT,
            user="\n".join(user_parts),
        )

        if response.stub:
            data = self._fallback(creator.name, creator.niche, creator.sub_niche)
            warnings = [
                "ANTHROPIC_API_KEY not configured — this positioning is a rule-based "
                "placeholder, not a model inference. Set the key to get a real synthesis."
            ]
        else:
            try:
                data = self._parse_json(response.text)
            except ValueError as exc:
                return AgentOutput(
                    status="failed",
                    summary="Model response could not be parsed as the expected JSON shape.",
                    confidence=0.0,
                    inputs_used=inputs_used,
                    warnings=[str(exc)],
                )
            warnings = []

        return AgentOutput(
            status="success",
            summary=f"Drafted a tentative positioning statement for {creator.name} from onboarding data alone.",
            # Low ceiling until this is re-run against real content history (Phase 5+).
            confidence=0.3,
            inputs_used=inputs_used,
            evidence_ids=[],
            proposed_state_changes=[{"type": "creator_profile_upsert", "data": data}],
            next_action="Ingest historical content so this can be re-run with real evidence.",
            warnings=warnings,
        )

    @staticmethod
    def _parse_json(text: str) -> dict:
        cleaned = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON from model: {exc}") from exc
        if "positioning_statement" not in data:
            raise ValueError("model JSON missing 'positioning_statement'")
        return data

    @staticmethod
    def _fallback(name: str, niche: str | None, sub_niche: str | None) -> dict:
        niche_phrase = sub_niche or niche or "their niche"
        return {
            "positioning_statement": (
                f"{name} is a creator building an audience around {niche_phrase}. "
                "This is a placeholder pending real analysis — see warnings."
            ),
            "expertise": [niche] if niche else [],
            "bio": f"{name} creates content about {niche_phrase}.",
        }
