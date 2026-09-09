"""Content Architect Agent (CLAUDE.md §11.6, §22).

Turns an approved content item (derived from an opportunity — see
app/domain/content/service.py::create_content_item_from_opportunity) into a
complete content brief: angle, hook, narrative structure, key points, CTA,
and everything else CLAUDE.md §22 lists as required brief fields. The brief
is what makes the Script Agent's job well-defined rather than a blank page.

No honest rule-based fallback exists (choosing an angle and structuring a
narrative needs real creative reasoning), so — like every other synthesis
job in this system — it is skipped outright in stub mode rather than
guessed.
"""

from app.agent_service.agents.base import BaseAgent
from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.schemas.creator import CreatorStateSnapshot

BRIEF_SYSTEM_PROMPT = """You are the Content Architect Agent inside a Creator \
Intelligence OS. You will be given a creator's positioning, voice, boundaries, \
audience segments, a specific content item's topic and format, the \
opportunity it was derived from (if any), and the research signals that \
justified that opportunity — each labeled with a signal id.

Produce a complete content brief for this one piece of content, including \
which audience segment (by its exact given name) it's speaking to — use \
null if none of the given segments clearly fit. Do not invent facts, \
statistics, or claims not supported by the given context — if you reference \
evidence, only cite the given signal ids. Respect the creator's boundaries \
(prohibited topics, avoided claims, rejected tones) absolutely; never \
propose content that crosses them.

If given strategic learnings from this creator's past performance (e.g. a \
hook type or pacing pattern that has been associated with above-baseline \
results), let them inform your choice of hook_type, hook, pacing, or \
narrative structure where relevant to this piece's format — but don't force \
a learning onto a piece it doesn't fit.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"objective": string, "audience_segment_name": string | null, \
"core_insight": string, "angle": string, \
"hook_type": string, "hook": string, \
"narrative_structure": {"section": "description", ...}, \
"key_points": string[], "examples": string[], "broll_suggestions": string[], \
"on_screen_text": string[], "pacing": string, "cta": string, \
"caption_concept": string, "cover_concept": string, \
"repurposing_opportunities": string[], "risk_notes": string, \
"evidence_signal_ids": string[]}
"""


class ContentArchitectAgent(BaseAgent):
    name = "content_architect"
    allowed_tools: list[str] = []

    async def run(
        self,
        context: CreatorStateSnapshot,
        model_router: ModelRouter,
        content_item: dict | None = None,
        opportunity: dict | None = None,
        pillar_name: str | None = None,
        evidence_signals: list[dict] | None = None,
    ) -> AgentOutput:
        content_item = content_item or {}
        evidence_signals = evidence_signals or []
        valid_ids = {s["id"] for s in evidence_signals}

        user_parts = []
        if context.positioning and context.positioning.positioning_statement:
            user_parts.append(f"Positioning: {context.positioning.positioning_statement}")
        if context.voice and context.voice.tone:
            user_parts.append(
                f"Voice: tone={context.voice.tone}, personality={context.voice.personality}, "
                f"cta_style={context.voice.cta_style}"
            )
        if context.positioning and context.positioning.prohibited_topics:
            user_parts.append(f"Prohibited topics: {', '.join(context.positioning.prohibited_topics)}")
        if context.positioning and context.positioning.avoided_claims:
            user_parts.append(f"Avoided claims: {', '.join(context.positioning.avoided_claims)}")
        if context.audience_segments:
            names = ", ".join(s.name for s in context.audience_segments)
            user_parts.append(f"Audience segments: {names}")
        if context.strategic_learnings:
            learning_lines = "\n".join(
                f"- {l['statement']} (confidence: {l['confidence']}, scope: {l['scope']})"
                for l in context.strategic_learnings
            )
            user_parts.append(f"Strategic learnings from past performance:\n{learning_lines}")

        user_parts.append(
            f"Content item: topic={content_item.get('topic')!r} format={content_item.get('format')!r}"
        )
        if pillar_name:
            user_parts.append(f"Content pillar: {pillar_name}")
        if opportunity:
            user_parts.append(
                f"Derived from opportunity: angle={opportunity.get('angle')!r} subtopic={opportunity.get('subtopic')!r}"
            )
        if evidence_signals:
            signal_lines = "\n".join(f"[{s['id']}] {s.get('topic')}: {s.get('summary', '')}" for s in evidence_signals)
            user_parts.append(f"Supporting research signals:\n{signal_lines}")

        response, failure = await self._complete_safely(
            model_router,
            tier=ModelTier.STANDARD,
            system=BRIEF_SYSTEM_PROMPT,
            user="\n\n".join(user_parts),
            label="Content brief",
            inputs_used=["content_item", "positioning", "voice", "strategic_learnings"],
            evidence_ids=list(valid_ids),
            # The brief's ~15-field JSON (several string-array fields) needs
            # more room than the router's conservative default — see the
            # max_tokens docstring on _complete_safely for why this isn't
            # just raised globally.
            max_tokens=1600,
        )
        if failure:
            return failure

        if response.stub:
            return AgentOutput(
                status="success",
                summary="Content brief: skipped (no model provider configured, and briefing has no honest rule-based fallback).",
                confidence=0.0,
                inputs_used=["content_item"],
                evidence_ids=list(valid_ids),
                warnings=[
                    "No ANTHROPIC_API_KEY or GROQ_API_KEY configured — briefing needs real creative "
                    "reasoning, so it was skipped rather than guessed."
                ],
            )

        try:
            data = self._parse_json(response.text, required_key="angle")
        except ValueError as exc:
            return AgentOutput(
                status="failed",
                summary="Content brief: model response could not be parsed as the expected JSON shape.",
                confidence=0.0,
                inputs_used=["content_item"],
                evidence_ids=list(valid_ids),
                warnings=[str(exc)],
            )

        cited_ids = [sid for sid in (data.get("evidence_signal_ids") or []) if sid in valid_ids]

        return AgentOutput(
            status="success",
            summary=f"Drafted a content brief for {content_item.get('topic')!r}.",
            confidence=0.5,
            inputs_used=["content_item", "positioning", "voice", "strategic_learnings"],
            evidence_ids=cited_ids,
            proposed_state_changes=[
                {"type": "content_brief_upsert", "data": data, "confidence": 0.5, "evidence_ids": cited_ids}
            ],
            next_action="Generate a script from this brief.",
            warnings=[],
        )
