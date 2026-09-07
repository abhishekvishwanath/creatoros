import pytest

from app.agent_service.agents.creator_intelligence import CreatorIntelligenceAgent


def test_parse_json_accepts_plain_json():
    data = CreatorIntelligenceAgent._parse_json(
        '{"positioning_statement": "x", "expertise": ["a"], "bio": "b"}'
    )
    assert data["positioning_statement"] == "x"


def test_parse_json_strips_markdown_fences():
    text = '```json\n{"positioning_statement": "x", "expertise": [], "bio": "b"}\n```'
    data = CreatorIntelligenceAgent._parse_json(text)
    assert data["positioning_statement"] == "x"


def test_parse_json_raises_on_invalid_json():
    with pytest.raises(ValueError):
        CreatorIntelligenceAgent._parse_json("not json at all")


def test_parse_json_raises_when_missing_required_field():
    with pytest.raises(ValueError):
        CreatorIntelligenceAgent._parse_json('{"expertise": ["a"]}')


def test_fallback_includes_niche_in_statement():
    data = CreatorIntelligenceAgent._fallback("Alice", "AI tools", None)
    assert "AI tools" in data["positioning_statement"]
    assert data["expertise"] == ["AI tools"]
