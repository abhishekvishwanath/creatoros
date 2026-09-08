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
    created_at: datetime

    model_config = {"from_attributes": True}
