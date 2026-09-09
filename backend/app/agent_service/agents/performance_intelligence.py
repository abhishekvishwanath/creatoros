"""Performance Intelligence Agent (CLAUDE.md §11.10, §27-29).

Diagnoses a published piece's performance against the creator's own
baseline (median of recent posts, overall and same-format — CLAUDE.md §28:
robust stats, not one absolute number) and proposes hedged, non-causal
readings of what's *associated* with the result (CLAUDE.md §29: "associated
with", "correlated with", "hypothesis" — never a flat causal claim from a
single data point).

The quantitative ratios (this piece's views vs. the creator's median views,
etc.) are computed in app/domain/performance/service.py::compute_ratios —
in code, not by the model — the model only reasons qualitatively about
*why*, over numbers it's already been given as fact (CLAUDE.md §20: no
opaque model-invented numbers).

No honest rule-based fallback exists for the "why" half (that's real
judgment), so this is skipped outright in stub mode, same as every other
synthesis agent. It's also skipped — not guessed — when there isn't enough
baseline history yet (CLAUDE.md §19: a small sample isn't definitive), since
"associated with" language over zero comparison points is just a guess
wearing hedged phrasing.
"""

from app.agent_service.agents.base import BaseAgent
from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.schemas.creator import CreatorStateSnapshot

PERFORMANCE_SYSTEM_PROMPT = """You are the Performance Intelligence Agent \
inside a Creator Intelligence OS. You will be given a published piece's \
metrics, its brief (angle/hook), its content pillar, and pre-computed \
ratios comparing its metrics to the creator's own baseline — treat these \
ratios as ground truth; do not recompute, second-guess, or contradict them.

Your job is to suggest what may be *associated* with this result — never \
claim certainty or direct causation from a single data point. Use hedged \
language such as "associated with", "appears to correlate with", or "a \
plausible hypothesis is". If the given context is too thin to say anything \
useful beyond the numbers themselves, say so honestly rather than inventing \
a factor.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"summary": string, "associated_factors": [{"factor": string, \
"confidence": "low" | "medium" | "high", "note": string}], \
"next_test": string | null, "confidence": "low" | "medium" | "high"}
"""


class PerformanceIntelligenceAgent(BaseAgent):
    name = "performance_intelligence"
    allowed_tools: list[str] = []

    async def run(
        self,
        context: CreatorStateSnapshot,
        model_router: ModelRouter,
        content_item: dict | None = None,
        brief: dict | None = None,
        pillar_name: str | None = None,
        snapshot: dict | None = None,
        baselines: dict | None = None,
        ratios: dict | None = None,
    ) -> AgentOutput:
        content_item = content_item or {}
        snapshot = snapshot or {}
        baselines = baselines or {}
        ratios = ratios or {}

        # `baselines` (not just `ratios`) is the real "do we have history"
        # signal: a metric whose baseline median happens to be exactly 0
        # produces no ratio (division by zero is undefined — see
        # compute_ratios) even though a real baseline exists. Gating on
        # `ratios` alone would misreport that case as "not enough history".
        if not baselines:
            return AgentOutput(
                status="success",
                summary=(
                    "Performance diagnosis: skipped — not enough of the creator's own publishing "
                    "history yet to compute a reliable baseline to compare against."
                ),
                confidence=0.0,
                inputs_used=["snapshot"],
                warnings=[
                    "Fewer than 3 prior posts (or same-format posts) with any metric recorded — "
                    "a baseline needs a real sample, not a guess."
                ],
            )

        user_parts = [f"Content: topic={content_item.get('topic')!r} format={content_item.get('format')!r}"]
        if pillar_name:
            user_parts.append(f"Pillar: {pillar_name}")
        if brief:
            user_parts.append(f"Angle: {brief.get('angle')}\nHook ({brief.get('hook_type')}): {brief.get('hook')}")
        user_parts.append(f"Metrics: {snapshot}")
        user_parts.append(f"Ratios vs creator baseline (pre-computed, treat as fact): {ratios}")
        user_parts.append(
            f"Raw creator baseline medians, for context on any metric with no ratio above "
            f"(e.g. a zero baseline median means this creator's posts typically get 0 of that "
            f"metric): {baselines}"
        )

        response, failure = await self._complete_safely(
            model_router,
            tier=ModelTier.STANDARD,
            system=PERFORMANCE_SYSTEM_PROMPT,
            user="\n\n".join(user_parts),
            label="Performance diagnosis",
            inputs_used=["snapshot", "baselines", "brief"],
            evidence_ids=[],
        )
        if failure:
            return failure

        if response.stub:
            return AgentOutput(
                status="success",
                summary="Performance diagnosis: skipped (no model provider configured, and diagnosis has no honest rule-based fallback).",
                confidence=0.0,
                inputs_used=["snapshot"],
                warnings=[
                    "No ANTHROPIC_API_KEY or GROQ_API_KEY configured — diagnosis needs real judgment, "
                    "so it was skipped rather than guessed."
                ],
            )

        try:
            data = self._parse_json(response.text, required_key="summary")
        except ValueError as exc:
            return AgentOutput(
                status="failed",
                summary="Performance diagnosis: model response could not be parsed as the expected JSON shape.",
                confidence=0.0,
                inputs_used=["snapshot"],
                warnings=[str(exc)],
            )

        return AgentOutput(
            status="success",
            summary=data.get("summary", ""),
            confidence=0.5,
            inputs_used=["snapshot", "baselines", "brief"],
            evidence_ids=[],
            proposed_state_changes=[
                {"type": "performance_diagnosis", "data": data, "confidence": 0.5, "evidence_ids": []}
            ],
            next_action=data.get("next_test"),
            warnings=[],
        )
