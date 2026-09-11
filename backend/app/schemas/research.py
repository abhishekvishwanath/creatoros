from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ResearchSignalCreate(BaseModel):
    """Manual research signal ingestion (CLAUDE.md §17.2) — no platform/search
    API is connected yet, so a creator (or whoever researches on their behalf)
    pastes in what they observed: a competitor post that took off, a trend,
    a recurring question from a forum. `summary` is the actual observation in
    the researcher's own words; the rest is structured metadata about it."""

    topic: str
    subtopic: Optional[str] = None
    format: Optional[str] = None
    summary: str
    platform: Optional[str] = None
    source_url: Optional[str] = None
    source_title: Optional[str] = None
    engagement: Optional[dict] = None


class ResearchSignalRead(BaseModel):
    id: str
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    format: Optional[str] = None
    engagement: Optional[dict] = None
    content_features: Optional[dict] = None
    hook_type: Optional[str] = None
    topic_cluster: Optional[str] = None
    evidence_quality: Optional[str] = None
    source_id: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class OpportunityEvidenceRead(BaseModel):
    research_signal_id: Optional[str] = None
    content_item_id: Optional[str] = None
    note: Optional[str] = None

    model_config = {"from_attributes": True}


class OpportunityRead(BaseModel):
    id: str
    topic: Optional[str] = None
    subtopic: Optional[str] = None
    angle: Optional[str] = None
    format: Optional[str] = None
    content_pillar_id: Optional[str] = None
    score: Optional[float] = None
    score_components: Optional[dict] = None
    competition_level: Optional[str] = None
    saturation_estimate: Optional[str] = None
    production_complexity: Optional[str] = None
    recommended_time_window: Optional[str] = None
    confidence: Optional[float] = None
    status: str
    created_at: datetime
    evidence: list[OpportunityEvidenceRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class GenerateOpportunitiesResponse(BaseModel):
    opportunities: list[OpportunityRead]
    warnings: list[str] = Field(default_factory=list)


class OpportunityStatusUpdate(BaseModel):
    status: Literal["approved", "rejected", "saved_for_later", "used"]


class TrendInsightRead(BaseModel):
    id: str
    topic: str
    signal_count: int
    recent_signal_count: int
    momentum: str
    saturation_estimate: Optional[str] = None
    durability: Optional[str] = None
    relevance_to_creator: Optional[str] = None
    reasoning: Optional[str] = None
    evidence_signal_ids: list[str] = Field(default_factory=list)
    confidence: Optional[float] = None
    analyzed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class AnalyzeTrendsResponse(BaseModel):
    insights: list[TrendInsightRead] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
