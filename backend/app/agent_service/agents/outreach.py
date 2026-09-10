"""Outreach Agent (CLAUDE.md §66, §70, Part II Phase 6).

Drafts outbound outreach messages (initial pitch, follow-ups) from an
already-generated campaign brief and the creator's voice — nothing more.

CLAUDE.md §66 is a hard, non-negotiable constraint on this agent
specifically: it may research, draft, and (starting Phase 7) classify a
brand's reply, but it may NEVER negotiate, counteroffer, accept, reject,
promise, or commit anything on the creator's behalf, and it may never write
to a thread's status/outcome/creator_decision fields — those are written
only by a route, only in response to an explicit creator action (enforced
in app/domain/commercial/service.py, not just here). This agent's output
is always a draft that a human must approve and send themselves
(CLAUDE.md §70 — draft-only, no send integration exists).
"""

from app.agent_service.agents.base import BaseAgent
from app.agent_service.model_router.router import ModelRouter, ModelTier
from app.agent_service.schemas.contracts import AgentOutput
from app.schemas.creator import CreatorStateSnapshot

OUTREACH_SYSTEM_PROMPT = """You are the Outreach Agent inside a Creator \
Intelligence OS. You DRAFT outreach messages only — you never send \
anything, and you never negotiate, offer, accept, or commit to anything on \
the creator's behalf. Everything you write is a starting draft a human \
will review, edit, approve, and send themselves.

You will be given a creator's voice, a brand, a campaign brief already \
prepared for this brand (pitch angle, why-this-brand, why-now, suggested \
CTA, personalization facts), the contact it's addressed to if known, and \
whether this is the initial pitch or a follow-up (with the prior messages \
in the thread, if any).

For an INITIAL PITCH: write a concise, personalized outreach email (not a \
generic template) in the creator's own voice. Reference the brief's \
personalization facts and why-now reasoning naturally — don't just list \
them. Address the contact by role if no name is given ("Hi there" if \
neither is known). Do not promise specific deliverables as if already \
agreed — the brief's suggested deliverables are a conversation starter, \
phrase them as an open question or proposal ("I'd love to explore something \
like ..."), never as a done deal. Do not state anything as fact that isn't \
in the given brand/brief information. End with a clear, low-pressure CTA.

For a FOLLOW-UP: keep it brief (2-4 sentences). Do not repeat the full \
pitch — reference that you reached out before, add one small piece of new \
value or context if the brief supports it, and restate the CTA. Never \
sound pushy or imply any commitment was made on either side.

Respond with ONLY a JSON object, no markdown fences, matching exactly:
{"subject": string, "body": string}
"""


class OutreachAgent(BaseAgent):
    name = "outreach"
    allowed_tools: list[str] = []

    async def run(
        self,
        context: CreatorStateSnapshot,
        model_router: ModelRouter,
        brand: dict | None = None,
        brief: dict | None = None,
        contact: dict | None = None,
        kind: str = "initial_pitch",
        prior_messages: list[dict] | None = None,
    ) -> AgentOutput:
        brand = brand or {}
        brief = brief or {}
        prior_messages = prior_messages or []

        user_parts = [f"Message kind: {kind}", f"Brand: {brand.get('name')!r} ({brand.get('category')})"]
        if contact:
            user_parts.append(f"Addressed to: name={contact.get('name')!r} role={contact.get('role')!r}")
        else:
            user_parts.append("Addressed to: no specific contact on file — address generically.")

        if brief.get("campaign_concept"):
            user_parts.append(f"Campaign concept: {brief['campaign_concept']}")
        if brief.get("pitch_angle"):
            user_parts.append(f"Pitch angle: {brief['pitch_angle']}")
        if brief.get("why_this_brand"):
            user_parts.append(f"Why this brand: {brief['why_this_brand']}")
        if brief.get("why_now"):
            user_parts.append(f"Why now: {brief['why_now']}")
        if brief.get("suggested_cta"):
            user_parts.append(f"Suggested CTA: {brief['suggested_cta']}")
        if brief.get("personalization_facts"):
            user_parts.append("Personalization facts: " + "; ".join(brief["personalization_facts"]))

        if context.voice and context.voice.tone:
            user_parts.append(
                f"Creator voice: tone={context.voice.tone}, personality={context.voice.personality}"
            )

        if kind == "follow_up":
            if prior_messages:
                history_lines = "\n".join(
                    f"[{m['direction']}/{m['kind']}] {m['body'][:300]}" for m in prior_messages
                )
                user_parts.append(f"Prior messages in this thread:\n{history_lines}")
            else:
                user_parts.append("Prior messages: none recorded — treat as a first check-in.")

        response, failure = await self._complete_safely(
            model_router,
            tier=ModelTier.STANDARD,
            system=OUTREACH_SYSTEM_PROMPT,
            user="\n\n".join(user_parts),
            label="Outreach draft",
            inputs_used=["brand", "brief", "contact", "voice"],
            evidence_ids=[],
        )
        if failure:
            return failure

        if response.stub:
            return AgentOutput(
                status="success",
                summary="Outreach draft: skipped (no model provider configured, and drafting has no honest rule-based fallback).",
                confidence=0.0,
                inputs_used=["brand"],
                evidence_ids=[],
                warnings=[
                    "No ANTHROPIC_API_KEY or GROQ_API_KEY configured — an outreach draft needs real "
                    "writing, so it was skipped rather than guessed."
                ],
            )

        try:
            data = self._parse_json(response.text, required_key="body")
        except ValueError as exc:
            return AgentOutput(
                status="failed",
                summary="Outreach draft: model response could not be parsed as the expected JSON shape.",
                confidence=0.0,
                inputs_used=["brand"],
                evidence_ids=[],
                warnings=[str(exc)],
            )

        body = data.get("body") or ""
        if not body.strip():
            return AgentOutput(
                status="failed",
                summary="Outreach draft: model returned an empty message body.",
                confidence=0.0,
                inputs_used=["brand"],
                evidence_ids=[],
                warnings=["Empty draft body."],
            )

        return AgentOutput(
            status="success",
            summary=f"Drafted a {kind.replace('_', ' ')} for {brand.get('name')!r}.",
            confidence=0.5,
            inputs_used=["brand", "brief", "contact", "voice"],
            evidence_ids=[],
            proposed_state_changes=[
                {
                    "type": "outreach_message_draft",
                    "data": {"subject": data.get("subject") or "", "body": body},
                    "confidence": 0.5,
                    "evidence_ids": [],
                }
            ],
            next_action="Review and approve this draft before sending.",
            warnings=[],
        )
