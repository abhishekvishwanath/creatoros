from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class PipelineRunRequest(BaseModel):
    youtube_url: Optional[str] = None


class PipelineStageRead(BaseModel):
    name: str
    status: str
    summary: Optional[str] = None
    warnings: list[str] = Field(default_factory=list)


class PipelineRunRead(BaseModel):
    id: str
    status: str
    youtube_url: Optional[str] = None
    stages: list[PipelineStageRead]
    error: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
