"""Audience Intelligence Agent (CLAUDE.md §19: Audience Problem Graph).

Two independent sub-jobs, mirroring CreatorIntelligenceAgent's structure —
each honest about its own evidence ceiling:

1. Profile — creator-wide demographics/psychographics/knowledge level,
   inferred from real audience signals (comments, questions, feedback the
   creator pasted in). Unlike positioning, there's no onboarding-only
   fallback: guessing who the audience *is* from the creator's niche alone
   would be exactly the "evidence over vibes" violation CLAUDE.md §3.4 warns
   against, so this is skipped entirely until at least one real signal
   exists.

2. Segments — the Audience Problem Graph itself: named clusters of
   problems/desires/objections/questions/fears/aspirations, only attempted
   once there's enough signal to call something a recurring pattern rather
   than one person's comment (same bar as content pillars). Additive by
   name rather than replacing: see app/domain/creator/service.py's
   apply_audience_segments.
"""

import asyncio

from app.agent_service.agents.base import BaseAgent
from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.schemas.creator import CreatorStateSnapshot

PROFILE_SYSTEM_PROMPT = """You are the Audience Intelligence Agent inside a \
Creator Intelligence OS. You will be given real comments, questions, or \
feedback a creator's audience has left, each labeled with a signal id, \
along with the creator's positioning.

Infer a creator-wide audience profile from these signals only: likely \
geography (if evident), demographics, psychographics (values, interests, \
pain points as a free-form object), knowledge_level (beginner/intermediate/\
advanced), purchase_intent (low/medium/high), and preferred_language.

Do not invent specifics the signals don't support — if a field can't be \
inferred, use null rather than guessing.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"geography": string[] | null, "demographics": object | null, \
"psychographics": object | null, "knowledge_level": string | null, \
"purchase_intent": string | null, "preferred_language": string | null}
"""

SEGMENTS_SYSTEM_PROMPT = """You are the Audience Intelligence Agent inside a \
Creator Intelligence OS. You will be given real comments, questions, or \
feedback a creator's audience has left, each labeled with a signal id.

Identify 1 to 4 audience segments — recurring clusters of people with \
similar problems, not a summary of each individual comment. Only propose a \
segment if at least two of the signals genuinely support it. For each \
segment, give a short descriptive name and its problems, desires, \
objections, questions, fears, aspirations (as string arrays — omit any list \
the signals don't support, don't pad with guesses), typical language \
patterns, and knowledge_level. Cite exactly which signal ids support each \
segment.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"segments": [{"name": string, "problems": string[], "desires": string[], \
"objections": string[], "questions": string[], "fears": string[], \
"aspirations": string[], "language": string[], "knowledge_level": string, \
"signal_ids": string[]}]}
"""

SEGMENT_ANALYSIS_MIN_ITEMS = 3


class AudienceIntelligenceAgent(BaseAgent):
    name = "audience_intelligence"
    allowed_tools: list[str] = []

    async def run(
        self,
        context: CreatorStateSnapshot,
        model_router: ModelRouter,
        audience_signals: list[dict] | None = None,
    ) -> AgentOutput:
        audience_signals = audience_signals or []
        if not audience_signals:
            return AgentOutput(
                status="success",
                summary="Audience: skipped, no audience signals have been ingested yet.",
                confidence=0.0,
                inputs_used=[],
                evidence_ids=[],
                proposed_state_changes=[],
                next_action="Ingest audience signals (comments, questions, feedback) before running Audience Intelligence.",
                warnings=["No audience signals available."],
            )

        tasks = [self._analyze_profile(context, audience_signals, model_router)]
        if len(audience_signals) >= SEGMENT_ANALYSIS_MIN_ITEMS:
            tasks.append(self._analyze_segments(audience_signals, model_router))

        outputs = await asyncio.gather(*tasks)
        if len(outputs) == 1:
            return outputs[0]
        return self._combine(outputs)

    async def _analyze_profile(
        self, context: CreatorStateSnapshot, audience_signals: list[dict], model_router: ModelRouter
    ) -> AgentOutput:
        evidence_ids = [s["id"] for s in audience_signals]
        user_parts = []
        if context.positioning and context.positioning.positioning_statement:
            user_parts.append(f"Creator positioning: {context.positioning.positioning_statement}")
        signal_lines = "\n".join(f"[{s['id']}] {s['text']}" for s in audience_signals)
        user_parts.append(f"Audience signals:\n{signal_lines}")

        response, failure = await self._complete_safely(
            model_router,
            tier=ModelTier.STANDARD,
            system=PROFILE_SYSTEM_PROMPT,
            user="\n\n".join(user_parts),
            label="Audience profile",
            inputs_used=["audience_signals"],
            evidence_ids=evidence_ids,
        )
        if failure:
            return failure

        if response.stub:
            return AgentOutput(
                status="success",
                summary="Audience profile: skipped (no model provider configured, and audience inference has no honest rule-based fallback).",
                confidence=0.0,
                inputs_used=["audience_signals"],
                evidence_ids=evidence_ids,
                warnings=[
                    "No ANTHROPIC_API_KEY or GROQ_API_KEY configured — audience profile inference needs a "
                    "real model read of the signals, so it was skipped rather than guessed."
                ],
            )

        try:
            data = self._parse_json(response.text, required_key="knowledge_level")
        except ValueError as exc:
            return AgentOutput(
                status="failed",
                summary="Audience profile: model response could not be parsed as the expected JSON shape.",
                confidence=0.0,
                inputs_used=["audience_signals"],
                evidence_ids=evidence_ids,
                warnings=[str(exc)],
            )

        # Confidence rises gently with sample size but stays capped — a
        # handful of comments is evidence, not a settled audience profile
        # (same shape as CreatorIntelligenceAgent._analyze_voice).
        confidence = min(0.3 + 0.05 * len(audience_signals), 0.6)

        return AgentOutput(
            status="success",
            summary=f"Inferred an audience profile from {len(audience_signals)} audience signal(s).",
            confidence=confidence,
            inputs_used=["audience_signals"],
            evidence_ids=evidence_ids,
            proposed_state_changes=[
                {
                    "type": "audience_profile_upsert",
                    "data": data,
                    "confidence": confidence,
                    "evidence_ids": evidence_ids,
                }
            ],
            next_action="Ingest more audience signals to raise confidence in this profile.",
            warnings=[],
        )

    async def _analyze_segments(
        self, audience_signals: list[dict], model_router: ModelRouter
    ) -> AgentOutput:
        all_ids = [s["id"] for s in audience_signals]
        signal_lines = "\n".join(f"[{s['id']}] {s['text']}" for s in audience_signals)

        response, failure = await self._complete_safely(
            model_router,
            tier=ModelTier.STANDARD,
            system=SEGMENTS_SYSTEM_PROMPT,
            user=signal_lines,
            label="Audience segments",
            inputs_used=["audience_signals"],
            evidence_ids=all_ids,
        )
        if failure:
            return failure

        if response.stub:
            return AgentOutput(
                status="success",
                summary="Audience segments: skipped (no model provider configured, and segment inference has no honest rule-based fallback).",
                confidence=0.0,
                inputs_used=["audience_signals"],
                evidence_ids=all_ids,
                warnings=[
                    "No ANTHROPIC_API_KEY or GROQ_API_KEY configured — segment inference needs a "
                    "real model read of the signals, so it was skipped rather than guessed."
                ],
            )

        try:
            data = self._parse_json(response.text, required_key="segments")
        except ValueError as exc:
            return AgentOutput(
                status="failed",
                summary="Audience segments: model response could not be parsed as the expected JSON shape.",
                confidence=0.0,
                inputs_used=["audience_signals"],
                evidence_ids=all_ids,
                warnings=[str(exc)],
            )

        # `.get("segments", [])`'s default only applies when the key is
        # *absent* — _parse_json's required_key check only verifies the key
        # exists, not that its value is non-null, so a model responding with
        # a literal `"segments": null` (a very plausible "found nothing"
        # answer) would otherwise pass a bare None into the loop below and
        # crash the whole sub-job instead of degrading to zero segments.
        raw_segments = data.get("segments") or []
        valid_ids = set(all_ids)
        # Same grounding discipline as pillars/opportunities/strategy: a
        # segment id list gets filtered down to real ids, and a segment left
        # with zero real citations after filtering is dropped entirely.
        segments = []
        for seg in raw_segments:
            real_ids = [sid for sid in seg.get("signal_ids", []) if sid in valid_ids]
            if real_ids:
                seg["evidence_ids"] = real_ids
                segments.append(seg)

        cited_ids = {sid for seg in segments for sid in seg["evidence_ids"]}
        coverage = len(cited_ids) / len(valid_ids) if valid_ids else 0.0
        confidence = self._coverage_confidence(coverage)
        for seg in segments:
            seg["confidence"] = confidence

        dropped = len(raw_segments) - len(segments)

        return AgentOutput(
            status="success",
            summary=f"Identified {len(segments)} audience segment(s) from {len(audience_signals)} signal(s).",
            confidence=confidence,
            inputs_used=["audience_signals"],
            evidence_ids=list(cited_ids),
            proposed_state_changes=[
                {
                    "type": "audience_segments_upsert",
                    "data": {"segments": segments},
                    "confidence": confidence,
                    "evidence_ids": list(cited_ids),
                }
            ]
            if segments
            else [],
            next_action="Ingest more audience signals to refine these segments." if segments else None,
            warnings=[f"Dropped {dropped} proposed segment(s) that cited no real signal id."] if dropped else [],
        )
