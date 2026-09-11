from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class ExperimentCreate(BaseModel):
    hypothesis: str
    variable: Optional[str] = None
    control_reference: Optional[str] = None
    planned_test_set: Optional[list] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None


class ExperimentRead(BaseModel):
    id: str
    hypothesis: str
    variable: Optional[str] = None
    control_reference: Optional[str] = None
    planned_test_set: Optional[list] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    status: str
    results: Optional[dict] = None
    confidence: Optional[str] = None
    conclusion: Optional[str] = None
    next_action: Optional[str] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class ExperimentStatusUpdate(BaseModel):
    status: Literal["running", "completed", "abandoned"]


class ExperimentResultCreate(BaseModel):
    content_item_id: Optional[str] = None
    metric_name: str
    metric_value: float
    group: Literal["test", "control"]


class ExperimentResultRead(BaseModel):
    id: str
    content_item_id: Optional[str] = None
    metric_name: str
    metric_value: float
    group: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ExperimentDetailRead(BaseModel):
    experiment: ExperimentRead
    results: list[ExperimentResultRead] = Field(default_factory=list)


class EvaluateExperimentResponse(BaseModel):
    experiment: Optional[ExperimentRead] = None
    stats: dict = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
