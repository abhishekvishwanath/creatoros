"""Experimentation Agent (CLAUDE.md §11.11, §30).

Reasons qualitatively over a rule-based comparison of an experiment's test
vs. control group results (app/domain/experiments/service.py::
compute_experiment_stats computes the medians/deltas in code — CLAUDE.md
§20: a model never invents or recomputes a number it's been given as fact).
The agent's only job is to judge, in hedged language (same discipline as
Performance Intelligence, CLAUDE.md §29), whether the data actually
supports the hypothesis, and whether the hypothesis is worth retaining as a
working belief for this creator or should be rejected.

No honest rule-based fallback exists for judging a hypothesis (that's real
judgment about a noisy real-world comparison), so this is skipped outright
in stub mode, same as every other synthesis agent.
"""

from app.agent_service.agents.base import BaseAgent
from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.schemas.creator import CreatorStateSnapshot

EXPERIMENTATION_SYSTEM_PROMPT = """You are the Experimentation Agent inside \
a Creator Intelligence OS. You will be given a creator's hypothesis, the \
variable being tested, what the control group represents, and — for one or \
more metrics — the pre-computed median of the test group, the median of the \
control group, their delta, and the sample size of each group. Treat these \
numbers as ground truth; do not recompute, second-guess, or invent numbers \
not given to you.

Judge whether the data actually supports the hypothesis. Use hedged \
language ("appears to support", "does not show a clear effect", "the \
sample is too thin to conclude anything even though the direction is \
positive") — never claim certainty from a noisy real-world comparison. A \
positive delta with a small sample is weaker evidence than the same delta \
with a larger one; say so explicitly when relevant. If multiple metrics \
disagree in direction, say so rather than picking whichever supports the \
hypothesis. Decide whether this hypothesis is worth retaining as a working \
belief for this creator (retain_hypothesis: true) or should be rejected/not \
acted on for now (false) — thin or contradictory evidence should lean \
false, not a hopeful true.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"conclusion": string, "confidence": "low" | "medium" | "high", \
"next_action": string, "retain_hypothesis": boolean}
"""


class ExperimentationAgent(BaseAgent):
    name = "experimentation"
    allowed_tools: list[str] = []

    async def run(
        self,
        context: CreatorStateSnapshot,
        model_router: ModelRouter,
        hypothesis: str | None = None,
        variable: str | None = None,
        control_reference: str | None = None,
        stats: dict | None = None,
    ) -> AgentOutput:
        stats = stats or {}
        adequate = {name: s for name, s in stats.items() if s.get("adequate_evidence")}

        if not adequate:
            return AgentOutput(
                status="success",
                summary=(
                    "Experiment evaluation: skipped — not enough results in both the test and "
                    "control groups yet for any metric to compare reliably."
                ),
                confidence=0.0,
                inputs_used=["stats"],
                warnings=[
                    "Each metric needs at least 2 results in both the test and control groups "
                    "before a comparison means anything."
                ],
            )

        user_parts = [f"Hypothesis: {hypothesis}"]
        if variable:
            user_parts.append(f"Variable being tested: {variable}")
        if control_reference:
            user_parts.append(f"Control group represents: {control_reference}")
        for metric_name, s in adequate.items():
            user_parts.append(
                f"Metric {metric_name!r}: test median={s['test_median']} (n={s['test_n']}), "
                f"control median={s['control_median']} (n={s['control_n']}), "
                f"delta={s.get('delta')}, pct_delta={s.get('pct_delta')}"
            )

        response, failure = await self._complete_safely(
            model_router,
            tier=ModelTier.STANDARD,
            system=EXPERIMENTATION_SYSTEM_PROMPT,
            user="\n\n".join(user_parts),
            label="Experiment evaluation",
            inputs_used=["hypothesis", "stats"],
            evidence_ids=[],
        )
        if failure:
            return failure

        if response.stub:
            return AgentOutput(
                status="success",
                summary="Experiment evaluation: skipped (no model provider configured, and judging a hypothesis has no honest rule-based fallback).",
                confidence=0.0,
                inputs_used=["hypothesis", "stats"],
                warnings=[
                    "No ANTHROPIC_API_KEY or GROQ_API_KEY configured — evaluating a hypothesis needs "
                    "real judgment, so it was skipped rather than guessed."
                ],
            )

        try:
            data = self._parse_json(response.text, required_key="conclusion")
        except ValueError as exc:
            return AgentOutput(
                status="failed",
                summary="Experiment evaluation: model response could not be parsed as the expected JSON shape.",
                confidence=0.0,
                inputs_used=["hypothesis", "stats"],
                warnings=[str(exc)],
            )

        return AgentOutput(
            status="success",
            summary=data.get("conclusion", ""),
            confidence=0.5,
            inputs_used=["hypothesis", "stats"],
            proposed_state_changes=[
                {"type": "experiment_evaluation", "data": data, "confidence": 0.5}
            ],
            next_action=data.get("next_action"),
            warnings=[],
        )
