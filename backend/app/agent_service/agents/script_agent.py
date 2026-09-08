"""Script Agent (CLAUDE.md §11.7, §23).

Writes a platform-native script from a content brief, in the creator's own
voice. Also handles the rewrite half of the writer → critic → rewriter loop
(CLAUDE.md §24): given the previous draft and the Editorial Critic's issues,
produce an improved version rather than starting over from the brief alone.

No honest rule-based fallback exists (writing is the whole job), so this is
skipped outright in stub mode.
"""

from app.agent_service.agents.base import BaseAgent
from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.schemas.creator import CreatorStateSnapshot

SCRIPT_SYSTEM_PROMPT = """You are the Script Agent inside a Creator \
Intelligence OS. You will be given a content brief and the creator's voice \
profile. Write a complete, platform-native script in that voice.

Do not invent facts, statistics, credentials, or claims beyond what the \
brief supports. Follow the brief's angle, hook, key points, and CTA — you \
are executing the brief, not replacing it. Also propose 2-3 alternate hook \
variants distinct from the brief's primary hook, so the creator has options.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"body": string, "hook_variants": string[]}
"""

REWRITE_SYSTEM_PROMPT = """You are the Script Agent inside a Creator \
Intelligence OS, rewriting a script draft that an editorial critique found \
issues with. You will be given the content brief, the creator's voice, the \
previous draft, and the critic's issues.

Address every issue directly while preserving what already worked. Do not \
invent facts beyond what the brief supports.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"body": string, "hook_variants": string[]}
"""


def _brief_summary(brief: dict) -> str:
    parts = [f"Objective: {brief.get('objective')}", f"Angle: {brief.get('angle')}"]
    if brief.get("hook"):
        parts.append(f"Hook ({brief.get('hook_type')}): {brief['hook']}")
    if brief.get("key_points"):
        parts.append("Key points: " + "; ".join(brief["key_points"]))
    if brief.get("cta"):
        parts.append(f"CTA: {brief['cta']}")
    return "\n".join(parts)


class ScriptAgent(BaseAgent):
    name = "script_agent"
    allowed_tools: list[str] = []

    async def run(
        self,
        context: CreatorStateSnapshot,
        model_router: ModelRouter,
        brief: dict | None = None,
        platform: str | None = None,
        previous_body: str | None = None,
        critic_issues: list[dict] | None = None,
    ) -> AgentOutput:
        brief = brief or {}
        is_rewrite = bool(previous_body)

        user_parts = [f"Platform: {platform or 'not specified'}", _brief_summary(brief)]
        if context.voice and context.voice.tone:
            user_parts.append(
                f"Voice: tone={context.voice.tone}, sentence_style={context.voice.sentence_style}, "
                f"personality={context.voice.personality}, signature_phrases={context.voice.signature_phrases}"
            )
        if is_rewrite:
            user_parts.append(f"Previous draft:\n{previous_body}")
            issues_text = "\n".join(
                f"- [{i.get('severity')}] {i.get('type')} ({i.get('location')}): {i.get('suggestion')}"
                for i in (critic_issues or [])
            )
            user_parts.append(f"Critic issues to address:\n{issues_text}")

        response, failure = await self._complete_safely(
            model_router,
            tier=ModelTier.STANDARD,
            system=REWRITE_SYSTEM_PROMPT if is_rewrite else SCRIPT_SYSTEM_PROMPT,
            user="\n\n".join(user_parts),
            label="Script rewrite" if is_rewrite else "Script",
            inputs_used=["brief", "voice"],
            evidence_ids=[],
        )
        if failure:
            return failure

        if response.stub:
            label = "Script rewrite" if is_rewrite else "Script"
            return AgentOutput(
                status="success",
                summary=f"{label}: skipped (no model provider configured, and writing has no honest rule-based fallback).",
                confidence=0.0,
                inputs_used=["brief"],
                warnings=[
                    "No ANTHROPIC_API_KEY or GROQ_API_KEY configured — writing needs a real model, "
                    "so it was skipped rather than guessed."
                ],
            )

        try:
            data = self._parse_json(response.text, required_key="body")
        except ValueError as exc:
            return AgentOutput(
                status="failed",
                summary="Script: model response could not be parsed as the expected JSON shape.",
                confidence=0.0,
                inputs_used=["brief"],
                warnings=[str(exc)],
            )

        return AgentOutput(
            status="success",
            summary="Rewrote the script addressing the critic's issues." if is_rewrite else "Drafted a script from the brief.",
            confidence=0.5,
            inputs_used=["brief", "voice"],
            evidence_ids=[],
            proposed_state_changes=[
                {
                    "type": "script_rewrite" if is_rewrite else "script_create",
                    "data": data,
                    "confidence": 0.5,
                    "evidence_ids": [],
                }
            ],
            next_action="Send this draft for editorial critique." if not is_rewrite else None,
            warnings=[],
        )
