"""Creator Intelligence Agent (CLAUDE.md §11.1).

Two independent sub-jobs, each honest about its own evidence ceiling:

1. Positioning — from onboarding fields alone (name, niche, business model,
   goals). There's no ingested content to ground this in yet, so it's kept
   explicitly low-confidence and framed as a hypothesis, never a settled fact
   (CLAUDE.md §5.3).

2. Voice — only attempted once the creator has ingested content with a
   transcript (Phase 4). Confidence scales mildly with how many transcripts
   were available, capped well below "high" until there's a real content
   history to draw on, and every claim is anchored to the specific content
   items it was inferred from (CLAUDE.md §3.4 evidence over vibes).
"""

import json
import re

from app.agent_service.agents.base import BaseAgent
from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.schemas.creator import CreatorStateSnapshot

POSITIONING_SYSTEM_PROMPT = """You are the Creator Intelligence Agent inside a Creator \
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

VOICE_SYSTEM_PROMPT = """You are the Creator Intelligence Agent inside a Creator \
Intelligence OS. You will be given excerpts from a creator's own past scripts, \
captions, or transcripts, each labeled with a content id. Infer their voice \
from these excerpts only — tone, sentence style, pacing, personality, humor \
level, storytelling style, opinion style, any recurring signature phrases, \
and their typical CTA style.

Do not invent traits the excerpts don't support. If the sample is too thin to \
say something confidently, say less rather than guessing.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"tone": string, "sentence_style": string, "pacing": string, "personality": string,
 "humor_level": string, "storytelling_style": string, "opinion_style": string,
 "signature_phrases": string[], "cta_style": string}
"""


class CreatorIntelligenceAgent(BaseAgent):
    name = "creator_intelligence"
    allowed_tools: list[str] = []

    async def run(
        self,
        context: CreatorStateSnapshot,
        model_router: ModelRouter,
        voice_transcripts: list[dict] | None = None,
    ) -> AgentOutput:
        positioning_output = await self._analyze_positioning(context, model_router)
        if not voice_transcripts:
            return positioning_output

        voice_output = await self._analyze_voice(voice_transcripts, model_router)

        # Each proposed_state_changes entry carries its own confidence/
        # evidence_ids (positioning and voice are different claims with
        # different evidence) — the top-level fields below are only a
        # summary of the combined run, not what gets written to the DB.
        #
        # Status must reflect a single sub-job failure honestly: collapsing
        # "positioning failed, voice succeeded" into "success" would silently
        # drop the positioning failure (and its warning) on the floor — the
        # caller needs "partial" to know one half didn't actually happen.
        failures = [o.status == "failed" for o in (positioning_output, voice_output)]
        if all(failures):
            combined_status = "failed"
        elif any(failures):
            combined_status = "partial"
        else:
            combined_status = "success"

        return AgentOutput(
            status=combined_status,
            summary=f"{positioning_output.summary} {voice_output.summary}",
            confidence=max(positioning_output.confidence, voice_output.confidence),
            inputs_used=positioning_output.inputs_used + voice_output.inputs_used,
            evidence_ids=positioning_output.evidence_ids + voice_output.evidence_ids,
            proposed_state_changes=positioning_output.proposed_state_changes
            + voice_output.proposed_state_changes,
            next_action=voice_output.next_action or positioning_output.next_action,
            warnings=positioning_output.warnings + voice_output.warnings,
        )

    async def _analyze_positioning(
        self, context: CreatorStateSnapshot, model_router: ModelRouter
    ) -> AgentOutput:
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
            system=POSITIONING_SYSTEM_PROMPT,
            user="\n".join(user_parts),
        )

        if response.stub:
            data = self._fallback_positioning(creator.name, creator.niche, creator.sub_niche)
            warnings = [
                "ANTHROPIC_API_KEY not configured — this positioning is a rule-based "
                "placeholder, not a model inference. Set the key to get a real synthesis."
            ]
        else:
            try:
                data = self._parse_json(response.text, required_key="positioning_statement")
            except ValueError as exc:
                return AgentOutput(
                    status="failed",
                    summary="Positioning: model response could not be parsed as the expected JSON shape.",
                    confidence=0.0,
                    inputs_used=inputs_used,
                    warnings=[str(exc)],
                )
            warnings = []

        return AgentOutput(
            status="success",
            summary=f"Drafted a tentative positioning statement for {creator.name} from onboarding data alone.",
            # Low ceiling until this is re-run against real content history.
            confidence=0.3,
            inputs_used=inputs_used,
            evidence_ids=[],
            proposed_state_changes=[
                {"type": "creator_profile_upsert", "data": data, "confidence": 0.3, "evidence_ids": []}
            ],
            next_action="Ingest historical content so this can be re-run with real evidence.",
            warnings=warnings,
        )

    async def _analyze_voice(
        self, voice_transcripts: list[dict], model_router: ModelRouter
    ) -> AgentOutput:
        evidence_ids = [t["id"] for t in voice_transcripts]
        excerpt_blocks = "\n\n".join(
            f"[{t['id']}] {t.get('title') or 'untitled'}:\n{t['transcript']}" for t in voice_transcripts
        )

        response = await model_router.complete(
            tier=ModelTier.STANDARD,
            system=VOICE_SYSTEM_PROMPT,
            user=excerpt_blocks,
        )

        if response.stub:
            return AgentOutput(
                status="success",
                summary="Voice: skipped (no ANTHROPIC_API_KEY configured, and voice inference has no honest rule-based fallback).",
                confidence=0.0,
                inputs_used=["content.transcripts"],
                evidence_ids=evidence_ids,
                warnings=[
                    "ANTHROPIC_API_KEY not configured — voice inference needs a real model "
                    "read of the transcripts, so it was skipped rather than guessed."
                ],
            )

        try:
            data = self._parse_json(response.text, required_key="tone")
        except ValueError as exc:
            return AgentOutput(
                status="failed",
                summary="Voice: model response could not be parsed as the expected JSON shape.",
                confidence=0.0,
                inputs_used=["content.transcripts"],
                evidence_ids=evidence_ids,
                warnings=[str(exc)],
            )

        # Confidence rises gently with sample size but stays capped — a
        # handful of transcripts is evidence, not a settled voice profile.
        confidence = min(0.3 + 0.08 * len(voice_transcripts), 0.6)

        return AgentOutput(
            status="success",
            summary=f"Inferred a voice profile from {len(voice_transcripts)} ingested content item(s).",
            confidence=confidence,
            inputs_used=["content.transcripts"],
            evidence_ids=evidence_ids,
            proposed_state_changes=[
                {
                    "type": "voice_profile_upsert",
                    "data": data,
                    "confidence": confidence,
                    "evidence_ids": evidence_ids,
                }
            ],
            next_action="Ingest more content to raise confidence in this voice profile.",
            warnings=[],
        )

    @staticmethod
    def _parse_json(text: str, *, required_key: str) -> dict:
        cleaned = re.sub(r"^```(json)?|```$", "", text.strip(), flags=re.MULTILINE).strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON from model: {exc}") from exc
        if required_key not in data:
            raise ValueError(f"model JSON missing '{required_key}'")
        return data

    @staticmethod
    def _fallback_positioning(name: str, niche: str | None, sub_niche: str | None) -> dict:
        niche_phrase = sub_niche or niche or "their niche"
        return {
            "positioning_statement": (
                f"{name} is a creator building an audience around {niche_phrase}. "
                "This is a placeholder pending real analysis — see warnings."
            ),
            "expertise": [niche] if niche else [],
            "bio": f"{name} creates content about {niche_phrase}.",
        }
