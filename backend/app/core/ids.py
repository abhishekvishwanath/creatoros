"""Human-readable prefixed IDs (CLAUDE.md 4.1: `creator_id = cr_<stable-unique-id>`).

Every core entity gets a stable, typed, prefixed identifier instead of a bare UUID so
IDs are traceable and self-describing wherever they show up in logs, evidence
references, or the UI (e.g. `cr_...`, `cnt_...`, `opp_...`).
"""

import uuid

PREFIXES = {
    "user": "usr",
    "creator": "cr",
    "social_account": "sac",
    "creator_profile": "cprof",
    "voice_profile": "voice",
    "audience_profile": "aud",
    "audience_segment": "seg",
    "audience_signal": "asig",
    "creator_goal": "goal",
    "creator_preference": "pref",
    "content_pillar": "pillar",
    "content_item": "cnt",
    "content_version": "cntv",
    "content_asset": "asset",
    "content_embedding": "emb",
    "published_content": "pub",
    "script": "scr",
    "content_brief": "brief",
    "calendar_event": "cal",
    "competitor": "comp",
    "research_source": "src",
    "research_signal": "sig",
    "opportunity": "opp",
    "opportunity_evidence": "ev",
    "strategy": "strat",
    "strategy_item": "strati",
    "performance_metric": "perf",
    "performance_snapshot": "psnap",
    "experiment": "exp",
    "experiment_result": "expr",
    "strategic_learning": "learn",
    "agent_run": "run",
    "agent_message": "msg",
    "agent_tool_call": "tool",
    "state_snapshot": "snap",
}


def generate_id(entity: str) -> str:
    prefix = PREFIXES.get(entity)
    if not prefix:
        raise ValueError(f"Unknown entity type for ID generation: {entity}")
    return f"{prefix}_{uuid.uuid4().hex[:16]}"
