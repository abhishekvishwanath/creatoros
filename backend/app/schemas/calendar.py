from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.schemas.content import ContentItemRead


class ScheduleContentRequest(BaseModel):
    scheduled_at: datetime
    platform: Optional[str] = None


class PublishContentRequest(BaseModel):
    url: Optional[str] = None
    external_id: Optional[str] = None


class CalendarEventRead(BaseModel):
    id: str
    content_item_id: Optional[str] = None
    content_title: Optional[str] = None
    content_status: Optional[str] = None
    content_format: Optional[str] = None
    scheduled_at: Optional[datetime] = None
    platform: Optional[str] = None
    status: str

    model_config = {"from_attributes": True}


class ScheduleContentResponse(BaseModel):
    item: ContentItemRead
    event: CalendarEventRead


class PublishContentResponse(BaseModel):
    item: ContentItemRead
    published_at: datetime
    url: Optional[str] = None


class BottleneckRead(BaseModel):
    type: str
    message: str
    evidence: dict


class CapacityRead(BaseModel):
    items_per_week: Optional[int] = None


class CapacityUpdate(BaseModel):
    items_per_week: int = Field(ge=1, le=50)
