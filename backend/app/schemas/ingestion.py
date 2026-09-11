from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class YoutubeImportRequest(BaseModel):
    url: str = Field(..., description="A YouTube channel URL, e.g. https://youtube.com/@handle")


class YoutubeImportResponse(BaseModel):
    channel_name: str
    social_account_id: str
    imported_count: int
    transcript_count: int
    warnings: list[str] = Field(default_factory=list)


class SocialAccountRead(BaseModel):
    id: str
    platform: str
    display_name: Optional[str] = None
    url: Optional[str] = None
    status: str
    last_synced_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
