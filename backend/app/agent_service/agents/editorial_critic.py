"""Editorial Critic Agent (CLAUDE.md §11.8, §24: writer → critic → rewriter).

Checks a script draft against creator voice, hook strength, specificity,
structure, CTA quality, factual claims, and brand boundaries. The first
draft is never assumed final (CLAUDE.md §24) — this agent's job is to find
what's wrong with it, structured enough that either a human or the Script
Agent's rewrite mode can act on it directly.

`passed` is computed in code from the model's score and issues, not trusted
as a raw model boolean (CLAUDE.md §20's "never trust an opaque model number"
principle applied to gating logic too): a script only passes with no
high-severity issue and a score at or above PASS_THRESHOLD.

No honest rule-based fallback exists (editorial judgment is the whole job),
so this is skipped outright in stub mode.
"""

from app.agent_service.agents.base import BaseAgent
from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.schemas.creator import CreatorStateSnapshot

PASS_THRESHOLD = 75

CRITIC_SYSTEM_PROMPT = """You are the Editorial Critic Agent inside a Creator \
Intelligence OS. You will be given a script draft, the brief it was written \
from, and the creator's voice and boundaries.

Evaluate the script honestly against: creator voice match, hook strength, \
specificity (vs generic filler), audience relevance, structure/pacing, \
repetition, CTA quality, platform fit, factual claims (flag anything that \
sounds invented or unverifiable), originality, and brand boundary \
violations (prohibited topics, avoided claims, rejected tones).

Give a score from 0 to 100 and list concrete issues — do not pad the issue \
list if the script is genuinely strong, and do not withhold real issues to \
be polite.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"score": number, "issues": [{"type": string, "severity": "low" | "medium" | "high", \
"location": string, "suggestion": string}]}
"""


class EditorialCriticAgent(BaseAgent):
    name = "editorial_critic"
    allowed_tools: list[str] = []

    async def run(
        self,
        context: CreatorStateSnapshot,
        model_router: ModelRouter,
        script_body: str | None = None,
        brief: dict | None = None,
    ) -> AgentOutput:
        brief = brief or {}
        user_parts = [f"Script:\n{script_body or ''}"]
        if brief:
            user_parts.append(f"Brief angle: {brief.get('angle')}\nBrief hook: {brief.get('hook')}")
        if context.voice and context.voice.tone:
            user_parts.append(f"Creator voice: tone={context.voice.tone}, personality={context.voice.personality}")
        if context.positioning and context.positioning.prohibited_topics:
            user_parts.append(f"Prohibited topics: {', '.join(context.positioning.prohibited_topics)}")
        if context.positioning and context.positioning.rejected_tones:
            user_parts.append(f"Rejected tones: {', '.join(context.positioning.rejected_tones)}")

        response, failure = await self._complete_safely(
            model_router,
            tier=ModelTier.STANDARD,
            system=CRITIC_SYSTEM_PROMPT,
            user="\n\n".join(user_parts),
            label="Editorial critique",
            inputs_used=["script", "brief", "voice"],
            evidence_ids=[],
        )
        if failure:
            return failure

        if response.stub:
            return AgentOutput(
                status="success",
                summary="Editorial critique: skipped (no model provider configured, and editorial judgment has no honest rule-based fallback).",
                confidence=0.0,
                inputs_used=["script"],
                warnings=[
                    "No ANTHROPIC_API_KEY or GROQ_API_KEY configured — critique needs real editorial "
                    "judgment, so it was skipped rather than guessed."
                ],
            )

        try:
            data = self._parse_json(response.text, required_key="score")
        except ValueError as exc:
            return AgentOutput(
                status="failed",
                summary="Editorial critique: model response could not be parsed as the expected JSON shape.",
                confidence=0.0,
                inputs_used=["script"],
                warnings=[str(exc)],
            )

        score = data.get("score", 0)
        issues = data.get("issues") or []
        # .lower(): the prompt asks for lowercase "high", but nothing
        # enforces that on the model side — a stray "High"/"HIGH" must still
        # block the pass, not silently defeat the gate on a formatting slip.
        passed = score >= PASS_THRESHOLD and not any(
            (i.get("severity") or "").lower() == "high" for i in issues
        )

        return AgentOutput(
            status="success",
            summary=f"Critiqued the script: score {score}, {'passed' if passed else 'needs a rewrite'}.",
            confidence=0.5,
            inputs_used=["script", "brief", "voice"],
            evidence_ids=[],
            proposed_state_changes=[
                {
                    "type": "script_critique",
                    "data": {"score": score, "issues": issues, "passed": passed},
                    "confidence": 0.5,
                    "evidence_ids": [],
                }
            ],
            next_action="Rewrite to address the issues." if not passed else "Ready for creator review.",
            warnings=[],
        )
