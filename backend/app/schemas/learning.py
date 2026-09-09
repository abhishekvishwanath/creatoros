from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class LearningRead(BaseModel):
    id: str
    statement: str
    category: Optional[str] = None
    evidence_ids: list[str] = Field(default_factory=list)
    confidence: float
    first_observed_at: datetime
    last_validated_at: Optional[datetime] = None
    status: str
    scope: str

    model_config = {"from_attributes": True}


class LearningStatusUpdate(BaseModel):
    status: Literal["active", "superseded", "retracted"]
