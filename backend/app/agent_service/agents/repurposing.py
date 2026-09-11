"""Repurposing Agent (CLAUDE.md §11.9, §25).

Turns one source asset's already-produced script/transcript into a
platform-native derivative — "1 YouTube video -> 3 Reels -> 1 Carousel ->
1 X thread -> ...". This is adaptation, not mechanical summarization
(CLAUDE.md §25): the derivative must preserve the source's actual claims and
examples, restructure them for the target platform's native conventions
(CLAUDE.md §23), stay in the creator's voice, and avoid just repeating the
source's phrasing verbatim. Like Content Architect and Script Agent, there
is no honest rule-based fallback for this (real creative adaptation), so it
is skipped outright in stub mode rather than guessed.
"""

from app.agent_service.agents.base import BaseAgent
from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.schemas.creator import CreatorStateSnapshot

REPURPOSING_SYSTEM_PROMPT = """You are the Repurposing Agent inside a Creator \
Intelligence OS. You will be given a creator's voice, one source content \
item (its topic and the full text of its script or transcript — this is \
ground truth), and a target platform + format to adapt it into.

Your job is adaptation, not summarization or transcription: restructure the \
source's actual claims, examples, and narrative into a piece that is native \
to the target format (CLAUDE.md platform-native structures — e.g. a short-\
form video needs a 0-2s hook and a fast payoff; a thread needs a strong \
opening tweet and one idea per subsequent post; a carousel needs one idea \
per slide; a newsletter can be longer and more narrative). Preserve the \
source's substance — never invent new facts, statistics, or examples not \
present in the source text. Never just paste or lightly reword the source \
text verbatim; if the target format genuinely can't avoid reusing a phrase \
(e.g. a signature line), that's fine, but the overall structure and pacing \
must actually change for the new format. Maintain the creator's voice \
(tone, vocabulary, personality) as given. Respect the creator's boundaries \
(prohibited topics, avoided claims) absolutely.

List the concrete transformations you made (e.g. "condensed the 3-example \
list into 1 representative example for the shorter format", "moved the \
mechanism explanation from the middle to the hook since threads front-load \
the strongest claim") so the creator can see exactly what changed and why \
(CLAUDE.md §25: expose important transformations, never a silent rewrite).

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"title": string, "body": string, "hook_variants": string[], \
"caption_concept": string, "transformations": string[]}
"""


class RepurposingAgent(BaseAgent):
    name = "repurposing"
    allowed_tools: list[str] = []

    async def run(
        self,
        context: CreatorStateSnapshot,
        model_router: ModelRouter,
        source_item: dict | None = None,
        source_text: str | None = None,
        target_platform: str | None = None,
        target_format: str | None = None,
    ) -> AgentOutput:
        source_item = source_item or {}

        if not source_text:
            return AgentOutput(
                status="failed",
                summary="Repurposing: the source content item has no script or transcript to adapt from.",
                confidence=0.0,
                inputs_used=["source_item"],
                warnings=["Generate or ingest a script/transcript on the source item before repurposing it."],
            )

        user_parts = []
        if context.voice and context.voice.tone:
            user_parts.append(
                f"Voice: tone={context.voice.tone}, personality={context.voice.personality}, "
                f"vocabulary={context.voice.vocabulary}, cta_style={context.voice.cta_style}"
            )
        if context.positioning and context.positioning.prohibited_topics:
            user_parts.append(f"Prohibited topics: {', '.join(context.positioning.prohibited_topics)}")
        if context.positioning and context.positioning.avoided_claims:
            user_parts.append(f"Avoided claims: {', '.join(context.positioning.avoided_claims)}")

        user_parts.append(
            f"Source content item: topic={source_item.get('topic')!r} "
            f"platform={source_item.get('platform')!r} format={source_item.get('format')!r}"
        )
        user_parts.append(f"Source text (ground truth — do not invent beyond this):\n{source_text}")
        user_parts.append(f"Target: platform={target_platform!r} format={target_format!r}")

        response, failure = await self._complete_safely(
            model_router,
            tier=ModelTier.STANDARD,
            system=REPURPOSING_SYSTEM_PROMPT,
            user="\n\n".join(user_parts),
            label="Repurposing",
            inputs_used=["source_item", "source_text", "voice"],
            evidence_ids=[],
            max_tokens=1400,
        )
        if failure:
            return failure

        if response.stub:
            return AgentOutput(
                status="success",
                summary="Repurposing: skipped (no model provider configured, and adaptation has no honest rule-based fallback).",
                confidence=0.0,
                inputs_used=["source_item"],
                warnings=[
                    "No ANTHROPIC_API_KEY or GROQ_API_KEY configured — repurposing needs real creative "
                    "adaptation, so it was skipped rather than guessed."
                ],
            )

        try:
            data = self._parse_json(response.text, required_key="body")
        except ValueError as exc:
            return AgentOutput(
                status="failed",
                summary="Repurposing: model response could not be parsed as the expected JSON shape.",
                confidence=0.0,
                inputs_used=["source_item", "source_text"],
                warnings=[str(exc)],
            )

        return AgentOutput(
            status="success",
            summary=f"Repurposed {source_item.get('topic')!r} into a {target_format} for {target_platform}.",
            confidence=0.5,
            inputs_used=["source_item", "source_text", "voice"],
            proposed_state_changes=[
                {"type": "repurposed_content_create", "data": data, "confidence": 0.5}
            ],
            next_action="Review the derivative and run the Editorial Critic on it like any other script.",
            warnings=[],
        )
