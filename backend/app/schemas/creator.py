from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from app.schemas.commercial import CommercialProfileRead


class CreatorCreate(BaseModel):
    email: EmailStr
    name: str
    niche: Optional[str] = None
    sub_niche: Optional[str] = None
    geography: Optional[str] = None
    languages: Optional[list[str]] = None
    business_model: Optional[str] = None
    monetization_model: Optional[str] = None


class CreatorRead(BaseModel):
    id: str
    name: str
    niche: Optional[str] = None
    sub_niche: Optional[str] = None
    geography: Optional[str] = None
    languages: Optional[list[str]] = None
    business_model: Optional[str] = None
    monetization_model: Optional[str] = None
    onboarding_status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CreatorCreateResponse(CreatorRead):
    """Onboarding-only response. Surfaces user_id so the frontend can hold onto
    it as the dev-mode X-Debug-User-Id credential (see app/api/deps.py TODO) —
    once real Supabase Auth is wired up, the session cookie/JWT replaces this
    and user_id no longer needs to appear in any API response."""

    user_id: str


class CreatorProfileRead(BaseModel):
    bio: Optional[str] = None
    expertise: Optional[list] = None
    positioning_statement: Optional[str] = None
    prohibited_topics: Optional[list] = None
    avoided_claims: Optional[list] = None
    rejected_tones: Optional[list] = None
    disclosure_requirements: Optional[list] = None
    confidence: float = 0.0

    model_config = {"from_attributes": True}


class VoiceProfileRead(BaseModel):
    tone: Optional[str] = None
    vocabulary: Optional[list] = None
    sentence_style: Optional[str] = None
    pacing: Optional[str] = None
    personality: Optional[str] = None
    humor_level: Optional[str] = None
    controversy_tolerance: Optional[str] = None
    storytelling_style: Optional[str] = None
    opinion_style: Optional[str] = None
    signature_phrases: Optional[list] = None
    cta_style: Optional[str] = None
    confidence: float = 0.0

    model_config = {"from_attributes": True}


class AudienceProfileRead(BaseModel):
    geography: Optional[list] = None
    demographics: Optional[dict] = None
    psychographics: Optional[dict] = None
    knowledge_level: Optional[str] = None
    purchase_intent: Optional[str] = None
    preferred_language: Optional[str] = None
    confidence: float = 0.0
    sample_size: Optional[int] = None

    model_config = {"from_attributes": True}


class AudienceSegmentRead(BaseModel):
    id: str
    name: str
    problems: Optional[list] = None
    desires: Optional[list] = None
    objections: Optional[list] = None
    questions: Optional[list] = None
    fears: Optional[list] = None
    aspirations: Optional[list] = None
    language: Optional[list] = None
    knowledge_level: Optional[str] = None
    confidence: float = 0.0
    sample_size: Optional[int] = None

    model_config = {"from_attributes": True}


class AudienceSignalCreate(BaseModel):
    """Manual audience signal ingestion (CLAUDE.md §19) — no comments/
    analytics API is connected yet, so a creator pastes in a comment,
    question, or piece of feedback they observed."""

    text: str
    source_platform: Optional[str] = None


class AudienceSignalRead(BaseModel):
    id: str
    text: str
    source_platform: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalyzeAudienceResponse(BaseModel):
    audience: Optional[AudienceProfileRead] = None
    segments: list[AudienceSegmentRead] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)


class CreatorGoalRead(BaseModel):
    id: str
    goal_type: str
    description: Optional[str] = None
    target_metric: Optional[str] = None
    target_value: Optional[float] = None
    priority: int = 0
    status: str

    model_config = {"from_attributes": True}


class CreatorStateSnapshot(BaseModel):
    """The bounded, task-specific working context for an agent run
    (CLAUDE.md 32). Never the raw database — a deliberately assembled subset."""

    creator: CreatorRead
    positioning: Optional[CreatorProfileRead] = None
    voice: Optional[VoiceProfileRead] = None
    audience: Optional[AudienceProfileRead] = None
    active_goals: list[CreatorGoalRead] = Field(default_factory=list)
    recent_content: list[dict] = Field(default_factory=list)
    content_pillars: list[dict] = Field(default_factory=list)
    audience_segments: list[AudienceSegmentRead] = Field(default_factory=list)
    top_performing_content: list[dict] = Field(default_factory=list)
    recent_failures: list[dict] = Field(default_factory=list)
    current_research_signals: list[dict] = Field(default_factory=list)
    active_experiments: list[dict] = Field(default_factory=list)
    strategic_learnings: list[dict] = Field(default_factory=list)
    commercial_profile: Optional[CommercialProfileRead] = None


class AnalyzeCreatorResponse(BaseModel):
    """Response for POST /creators/{id}/analyze. Distinct from
    CreatorStateSnapshot (which represents pure state) because an analyze run
    can partially fail — e.g. positioning inference fails while voice
    inference succeeds — and the caller needs to see that instead of it being
    silently dropped (CLAUDE.md §43: never let a failure look like success)."""

    state: CreatorStateSnapshot
    warnings: list[str] = Field(default_factory=list)
