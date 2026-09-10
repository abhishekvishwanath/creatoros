from typing import Optional

from pydantic import BaseModel


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
