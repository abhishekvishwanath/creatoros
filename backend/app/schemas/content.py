from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ContentItemCreate(BaseModel):
    title: str
    platform: Optional[str] = None
    format: Optional[str] = None
    topic: Optional[str] = None
    transcript: Optional[str] = Field(
        default=None,
        description="Script, caption, or transcript text — the raw material voice/topic analysis reads from.",
    )


class ContentItemRead(BaseModel):
    id: str
    title: Optional[str] = None
    platform: Optional[str] = None
    format: Optional[str] = None
    topic: Optional[str] = None
    status: str
    source_type: str
    transcript: Optional[str] = None
    opportunity_id: Optional[str] = None
    pillar_id: Optional[str] = None
    source_content_item_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ContentItemFromOpportunityCreate(BaseModel):
    opportunity_id: str


class ContentBriefRead(BaseModel):
    id: str
    objective: Optional[str] = None
    audience_segment_id: Optional[str] = None
    core_insight: Optional[str] = None
    angle: Optional[str] = None
    hook_type: Optional[str] = None
    hook: Optional[str] = None
    narrative_structure: Optional[dict] = None
    # Typed as list[str] (not bare `list`) so a malformed agent output shape
    # — e.g. a model returning a key point as a nested object instead of a
    # string — is caught by _validate_or_502 (app/api/routes/content.py)
    # instead of silently reaching the frontend, which renders these
    # directly as React children and would crash on anything but a string.
    key_points: Optional[list[str]] = None
    examples: Optional[list[str]] = None
    broll_suggestions: Optional[list[str]] = None
    on_screen_text: Optional[list[str]] = None
    pacing: Optional[str] = None
    cta: Optional[str] = None
    caption_concept: Optional[str] = None
    cover_concept: Optional[str] = None
    repurposing_opportunities: Optional[list[str]] = None
    evidence_ids: Optional[list[str]] = None
    risk_notes: Optional[str] = None

    model_config = {"from_attributes": True}


class CriticIssue(BaseModel):
    type: str
    severity: str
    location: str
    suggestion: str


class ScriptRead(BaseModel):
    id: str
    brief_id: Optional[str] = None
    version_number: int
    platform: Optional[str] = None
    body: str
    hook_variants: Optional[list[str]] = None
    status: str
    critic_score: Optional[int] = None
    critic_issues: Optional[list[CriticIssue]] = None

    model_config = {"from_attributes": True}


class ContentDetailRead(BaseModel):
    item: ContentItemRead
    brief: Optional[ContentBriefRead] = None
    scripts: list[ScriptRead] = Field(default_factory=list)


class GenerateBriefResponse(BaseModel):
    brief: Optional[ContentBriefRead] = None
    warnings: list[str] = Field(default_factory=list)


class GenerateScriptResponse(BaseModel):
    script: Optional[ScriptRead] = None
    warnings: list[str] = Field(default_factory=list)


class ReviewScriptRequest(BaseModel):
    script_id: str


class ReviewScriptResponse(BaseModel):
    reviewed: Optional[ScriptRead] = None
    rewrite: Optional[ScriptRead] = None
    warnings: list[str] = Field(default_factory=list)


class RepurposeContentRequest(BaseModel):
    target_platform: str
    target_format: str


class RepurposeContentResponse(BaseModel):
    derivative: Optional[ContentItemRead] = None
    script: Optional[ScriptRead] = None
    caption_concept: Optional[str] = None
    transformations: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
