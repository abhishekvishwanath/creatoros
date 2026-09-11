"""Trend Intelligence Agent (CLAUDE.md §11.4).

Reasons over topic clusters drawn from this creator's own ingested research
signals (app/domain/research/service.py::build_trend_analysis_context) —
manual entry today, per CLAUDE.md §69, but still real observed material,
just not fetched live from a platform API. Momentum (rising/stable/
declining/new) and signal counts are computed in code, never by the model
(CLAUDE.md §20) — this agent's only job is the qualitative half CLAUDE.md
§11.4 actually needs judgment for: estimating saturation, telling a
temporary spike apart from a durable pattern, and ranking relevance to
*this* creator specifically (never equate trendiness with relevance).

No honest rule-based fallback exists for that judgment, so this is skipped
outright in stub mode, same as every other synthesis agent.
"""

from app.agent_service.agents.base import BaseAgent
from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.schemas.creator import CreatorStateSnapshot

TREND_SYSTEM_PROMPT = """You are the Trend Intelligence Agent inside a \
Creator Intelligence OS. You will be given a creator's positioning, \
audience, and content pillars, plus a list of topic clusters drawn from \
their own research signals. For each topic you are given its signal count, \
recent signal count, and a pre-computed momentum (rising/stable/declining/ \
new) — treat momentum as ground truth; do not recompute, second-guess, or \
contradict it. You are also given a few representative signal summaries \
per topic.

For each topic, judge:
- saturation_estimate: how crowded this topic already looks based on the \
given signals (low/medium/high) — many signals describing many different \
creators/sources covering it suggests high saturation; a topic with few \
signals or one dominant unique angle suggests low.
- durability: whether this looks like a temporary_spike (a one-off event, \
news cycle, or single viral post) or a durable pattern worth building on, \
based on the momentum and what the summaries actually describe — use \
"unclear" honestly when the evidence doesn't clearly support either.
- relevance_to_creator: low/medium/high, based on fit with THIS creator's \
positioning, audience, and pillars — never equate trendiness with \
relevance; a rising topic with no fit to this creator is low relevance.
- reasoning: 1-2 sentences grounding your judgment in the given signals, \
never inventing details beyond them.
- confidence: low/medium/high, reflecting how much real signal you were \
actually given for this topic (few signals = lower confidence).

Only return insights for topics you were given — never introduce a new \
topic. Use each topic's exact given topic_key.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"insights": [{"topic_key": string, "saturation_estimate": "low" | "medium" | "high", \
"durability": "temporary_spike" | "durable" | "unclear", \
"relevance_to_creator": "low" | "medium" | "high", "reasoning": string, \
"confidence": "low" | "medium" | "high"}]}
"""


class TrendIntelligenceAgent(BaseAgent):
    name = "trend_intelligence"
    allowed_tools: list[str] = []

    async def run(
        self,
        context: CreatorStateSnapshot,
        model_router: ModelRouter,
        topics: list[dict] | None = None,
    ) -> AgentOutput:
        topics = topics or []

        if not topics:
            return AgentOutput(
                status="success",
                summary="Trend analysis: skipped — no research signals with a topic to analyze yet.",
                confidence=0.0,
                inputs_used=["topics"],
                warnings=["Add research signals with a topic before running trend analysis."],
            )

        valid_keys = {t["topic_key"] for t in topics}

        user_parts = []
        if context.positioning and context.positioning.positioning_statement:
            user_parts.append(f"Positioning: {context.positioning.positioning_statement}")
        if context.audience_segments:
            for segment in context.audience_segments:
                if segment.problems:
                    user_parts.append(f"Audience segment {segment.name!r} problems: {', '.join(segment.problems)}")
        if context.content_pillars:
            pillar_names = ", ".join(p["name"] for p in context.content_pillars)
            user_parts.append(f"Content pillars: {pillar_names}")

        for t in topics:
            summaries = "; ".join(t.get("summaries") or []) or "(no summary text given)"
            user_parts.append(
                f"Topic [{t['topic_key']}] {t['topic']!r}: signal_count={t['signal_count']}, "
                f"recent_signal_count={t['recent_signal_count']}, momentum={t['momentum']!r}. "
                f"Sample signals: {summaries}"
            )

        response, failure = await self._complete_safely(
            model_router,
            tier=ModelTier.STANDARD,
            system=TREND_SYSTEM_PROMPT,
            user="\n\n".join(user_parts),
            label="Trend analysis",
            inputs_used=["topics", "positioning", "audience", "content_pillars"],
            evidence_ids=[],
            max_tokens=1400,
        )
        if failure:
            return failure

        if response.stub:
            return AgentOutput(
                status="success",
                summary="Trend analysis: skipped (no model provider configured, and judging saturation/durability/relevance has no honest rule-based fallback).",
                confidence=0.0,
                inputs_used=["topics"],
                warnings=[
                    "No ANTHROPIC_API_KEY or GROQ_API_KEY configured — trend analysis needs real "
                    "judgment, so it was skipped rather than guessed."
                ],
            )

        try:
            data = self._parse_json(response.text, required_key="insights")
        except ValueError as exc:
            return AgentOutput(
                status="failed",
                summary="Trend analysis: model response could not be parsed as the expected JSON shape.",
                confidence=0.0,
                inputs_used=["topics"],
                warnings=[str(exc)],
            )

        insights = [i for i in data.get("insights", []) if i.get("topic_key") in valid_keys]
        dropped = len(data.get("insights", [])) - len(insights)

        return AgentOutput(
            status="success",
            summary=f"Analyzed {len(insights)} topic(s) from {len(topics)} given.",
            confidence=0.5,
            inputs_used=["topics", "positioning", "audience", "content_pillars"],
            proposed_state_changes=[
                {"type": "trend_insights", "data": {"insights": insights}, "confidence": 0.5}
            ],
            warnings=[f"Dropped {dropped} insight(s) for a topic not given to the model."] if dropped else [],
        )
