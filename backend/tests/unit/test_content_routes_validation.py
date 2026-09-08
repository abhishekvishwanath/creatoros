import pytest
from fastapi import HTTPException

from app.api.routes.content import _validate_or_502
from app.schemas.content import ContentBriefRead


class _FakeBrief:
    """Stands in for a freshly-written ContentBrief ORM row whose
    `key_points` ended up as a string instead of a list — a plausible model
    output slip `_parse_json` doesn't catch (it only checks that the
    required key is present, not its shape)."""

    id = "brief_1"
    objective = None
    core_insight = None
    angle = "a"
    hook_type = None
    hook = None
    narrative_structure = None
    key_points = "not a list"
    examples = None
    broll_suggestions = None
    on_screen_text = None
    pacing = None
    cta = None
    caption_concept = None
    cover_concept = None
    repurposing_opportunities = None
    evidence_ids = None
    risk_notes = None


def test_validate_or_502_raises_a_clean_http_exception_on_malformed_shape():
    """Regression test: a malformed agent output shape must surface as a
    502 the caller can handle, not an unhandled pydantic ValidationError
    that FastAPI would otherwise turn into a bare 500."""
    with pytest.raises(HTTPException) as exc_info:
        _validate_or_502(ContentBriefRead, _FakeBrief(), label="Content Architect")

    assert exc_info.value.status_code == 502
    assert "Content Architect" in exc_info.value.detail


def test_validate_or_502_passes_through_a_valid_shape():
    _FakeBrief.key_points = ["a", "b"]
    result = _validate_or_502(ContentBriefRead, _FakeBrief(), label="Content Architect")
    assert result.key_points == ["a", "b"]
