from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PerformanceSnapshotCreate(BaseModel):
    views: Optional[int] = None
    watch_time: Optional[float] = None
    avg_view_duration: Optional[float] = None
    retention: Optional[float] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    saves: Optional[int] = None
    followers_gained: Optional[int] = None
    profile_visits: Optional[int] = None
    captured_at: Optional[datetime] = None


class PerformanceSnapshotRead(BaseModel):
    id: str
    content_item_id: str
    views: Optional[int] = None
    watch_time: Optional[float] = None
    avg_view_duration: Optional[float] = None
    retention: Optional[float] = None
    likes: Optional[int] = None
    comments: Optional[int] = None
    shares: Optional[int] = None
    saves: Optional[int] = None
    followers_gained: Optional[int] = None
    profile_visits: Optional[int] = None
    baseline_comparison: Optional[dict] = None
    captured_at: datetime

    model_config = {"from_attributes": True}


class AssociatedFactor(BaseModel):
    factor: str
    confidence: str
    note: str


class DiagnosisRead(BaseModel):
    summary: str
    associated_factors: list[AssociatedFactor] = Field(default_factory=list)
    next_test: Optional[str] = None
    confidence: str


class DiagnoseResponse(BaseModel):
    snapshot: PerformanceSnapshotRead
    diagnosis: Optional[DiagnosisRead] = None
    warnings: list[str] = Field(default_factory=list)


class PerformanceOverviewItem(BaseModel):
    content_item_id: str
    title: Optional[str] = None
    topic: Optional[str] = None
    format: Optional[str] = None
    platform: Optional[str] = None
    latest_snapshot: Optional[PerformanceSnapshotRead] = None
