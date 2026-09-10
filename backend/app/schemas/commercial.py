from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CommercialProfileRead(BaseModel):
    id: str
    version: int
    # Nullable JSON columns: a field stays None until it's set at least once
    # (apply_commercial_profile_update falls back to None, not [], when
    # neither the update nor the prior version has a value for it) — an
    # empty-list default here would misrepresent "never set" as "set to
    # nothing".
    ideal_sponsor_categories: Optional[list[str]] = None
    prohibited_categories: Optional[list[str]] = None
    target_geographies: Optional[list[str]] = None
    preferred_deal_formats: Optional[list[str]] = None
    minimum_conditions: Optional[str] = None
    exclusivity_constraints: Optional[str] = None
    usage_rights_preferences: Optional[str] = None
    sponsorship_goals: Optional[str] = None
    revenue_goal: Optional[str] = None
    brands_to_avoid: Optional[list[str]] = None
    confidence: float

    model_config = {"from_attributes": True}


class CommercialProfileUpdate(BaseModel):
    """Partial update — an *unset* (absent) field leaves the current value
    untouched (CLAUDE.md §15, see apply_commercial_profile_update); a field
    sent as `""`/`[]` clears it. The manual-entry form on the Creator DNA
    page always sends every field (its complete current display state), so
    for that caller "blank" and "clear" mean the same thing — this schema
    doesn't try to distinguish "creator left it blank" from "creator
    explicitly wants it empty" the way an agent's partial proposal must
    distinguish "can't infer this" (send null) from "infer it as empty"."""

    ideal_sponsor_categories: Optional[list[str]] = None
    prohibited_categories: Optional[list[str]] = None
    target_geographies: Optional[list[str]] = None
    preferred_deal_formats: Optional[list[str]] = None
    minimum_conditions: Optional[str] = None
    exclusivity_constraints: Optional[str] = None
    usage_rights_preferences: Optional[str] = None
    sponsorship_goals: Optional[str] = None
    revenue_goal: Optional[str] = None
    brands_to_avoid: Optional[list[str]] = None


class BrandCreate(BaseModel):
    name: str
    website: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    geography: Optional[str] = None
    target_customer: Optional[list[str]] = None
    products: Optional[list[str]] = None
    positioning: Optional[str] = None
    competitors: Optional[list[str]] = None


class BrandRead(BaseModel):
    id: str
    name: str
    website: Optional[str] = None
    category: Optional[str] = None
    subcategory: Optional[str] = None
    description: Optional[str] = None
    geography: Optional[str] = None
    target_customer: Optional[list[str]] = None
    products: Optional[list[str]] = None
    positioning: Optional[str] = None
    competitors: Optional[list[str]] = None
    source: str
    confidence: float
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}


class BrandContactCreate(BaseModel):
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    email: Optional[str] = None
    profile_url: Optional[str] = None
    source: Optional[str] = None
    verification_state: str = "unverified"


class BrandContactRead(BaseModel):
    id: str
    brand_id: str
    name: Optional[str] = None
    role: Optional[str] = None
    department: Optional[str] = None
    email: Optional[str] = None
    profile_url: Optional[str] = None
    source: Optional[str] = None
    verification_state: str
    confidence: float
    last_verified_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class BrandSignalCreate(BaseModel):
    signal_type: Optional[str] = None
    summary: str
    source_url: Optional[str] = None
    source_note: Optional[str] = None
    observed_at: Optional[datetime] = None
    evidence_quality: Optional[str] = "medium"


class BrandOpportunityRead(BaseModel):
    id: str
    brand_id: str
    score: Optional[float] = None
    score_components: Optional[dict] = None
    reasons: Optional[str] = None
    evidence_signal_ids: list[str] = Field(default_factory=list)
    suggested_contact_roles: list[str] = Field(default_factory=list)
    confidence: float
    status: str
    prohibited_conflict: bool = False

    model_config = {"from_attributes": True}


class ScoreBrandOpportunityResponse(BaseModel):
    opportunity: Optional[BrandOpportunityRead] = None
    warnings: list[str] = Field(default_factory=list)


class BrandRadarItem(BaseModel):
    brand: BrandRead
    opportunity: BrandOpportunityRead


class BrandSignalRead(BaseModel):
    id: str
    brand_id: Optional[str] = None
    signal_type: Optional[str] = None
    summary: str
    source_url: Optional[str] = None
    source_note: Optional[str] = None
    observed_at: Optional[datetime] = None
    retrieved_at: datetime
    evidence_quality: Optional[str] = None

    model_config = {"from_attributes": True}
