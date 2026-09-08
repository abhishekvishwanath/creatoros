from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class StrategyItemRead(BaseModel):
    id: str
    opportunity_id: Optional[str] = None
    opportunity_topic: Optional[str] = None
    day_of_week: Optional[int] = None
    portfolio_role: Optional[str] = None
    status: str

    model_config = {"from_attributes": True}


class StrategyRead(BaseModel):
    id: str
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    summary: Optional[str] = None
    status: str
    confidence: Optional[float] = None
    created_at: datetime
    items: list[StrategyItemRead] = Field(default_factory=list)

    model_config = {"from_attributes": True}


class GenerateStrategyResponse(BaseModel):
    strategy: Optional[StrategyRead] = None
    warnings: list[str] = Field(default_factory=list)


class StrategyStatusUpdate(BaseModel):
    status: Literal["draft", "active", "completed"]
