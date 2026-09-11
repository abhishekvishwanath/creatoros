from app.domain.ingestion.youtube_search import _parse_search_results

SAMPLE_SEARCH_HTML = """<html><head></head><body><script>var ytInitialData = {
"contents": {"twoColumnSearchResultsRenderer": {"primaryContents": {"sectionListRenderer": {"contents": [
{"itemSectionRenderer": {"contents": [
  {"videoRenderer": {
    "videoId": "abc123",
    "title": {"runs": [{"text": "iPhone 18 Pro Review"}]},
    "ownerText": {"runs": [{"text": "Some Tech Channel"}]},
    "viewCountText": {"simpleText": "1,602,196 views"}
  }},
  {"videoRenderer": {
    "videoId": "def456",
    "title": {"runs": [{"text": "Best Budget Phones 2026"}]},
    "ownerText": {"runs": [{"text": "Another Channel"}]},
    "viewCountText": {"simpleText": "988,759 views"}
  }},
  {"searchRefinementCardRenderer": {"unrelatedNoise": true}}
]}}
]}}}},
"other": "irrelevant nested stuff"
};</script></body></html>
"""


def test_parse_search_results_extracts_video_renderers():
    results = _parse_search_results(SAMPLE_SEARCH_HTML, limit=10)
    assert len(results) == 2
    assert results[0]["video_id"] == "abc123"
    assert results[0]["title"] == "iPhone 18 Pro Review"
    assert results[0]["channel"] == "Some Tech Channel"
    assert results[0]["views"] == "1,602,196 views"
    assert results[0]["url"] == "https://www.youtube.com/watch?v=abc123"


def test_parse_search_results_respects_limit():
    results = _parse_search_results(SAMPLE_SEARCH_HTML, limit=1)
    assert len(results) == 1


def test_parse_search_results_missing_ytinitialdata_returns_empty():
    assert _parse_search_results("<html>no data here</html>", limit=10) == []


def test_parse_search_results_malformed_json_returns_empty():
    html = "<script>var ytInitialData = {not valid json};</script>"
    assert _parse_search_results(html, limit=10) == []


def test_parse_search_results_ignores_renderers_missing_required_fields():
    html = """<script>var ytInitialData = {
    "a": {"videoRenderer": {"title": {"runs": [{"text": "No video id here"}]}}}
    };</script>"""
    assert _parse_search_results(html, limit=10) == []
