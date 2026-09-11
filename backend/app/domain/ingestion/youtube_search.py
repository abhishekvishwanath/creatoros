"""YouTube search (CLAUDE.md §11.3, §17.1): the Research Agent's missing
live-fetch half. Given a topic/niche query, returns real, current videos —
title, channel, view count, URL — pulled from YouTube's public search
results page, the same unauthenticated technique as youtube.py's channel
resolution (no API key, no login, no scraping of anything access-gated).

This is what lets the "paste a link, everything starts" pipeline generate
real Opportunity/Trend evidence immediately after a YouTube import, instead
of requiring the creator to hand-paste research signals first.
"""

import json
import logging
import re
from urllib.parse import quote

import httpx

from app.domain.ingestion.youtube import _consent_headers

logger = logging.getLogger(__name__)

_TIMEOUT = 10.0
_YT_INITIAL_DATA_RE = re.compile(r"var ytInitialData = ({.*?});</script>", re.DOTALL)


async def search_videos(query: str, *, limit: int = 5) -> list[dict]:
    """Each item: {video_id, title, channel, views, url}. Returns [] (never
    raises) on any fetch/parse failure — this is enrichment for the
    auto-pipeline, not a precondition for it (CLAUDE.md §43)."""
    if not query.strip():
        return []
    url = f"https://www.youtube.com/results?search_query={quote(query.strip())}"
    try:
        # search results haven't been observed hitting the EU consent wall
        # (unlike the channel page), but reusing youtube.py's consent
        # cookie here is free insurance rather than a second guess to
        # maintain (see youtube.py's _consent_headers for the story).
        async with httpx.AsyncClient(headers=_consent_headers(), timeout=_TIMEOUT) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError:
        logger.warning("YouTube search fetch failed for query %r", query, exc_info=True)
        return []

    return _parse_search_results(response.text, limit=limit)


def _parse_search_results(html: str, *, limit: int) -> list[dict]:
    """Pure parsing half, split out for unit testing without a network call
    (same pattern as youtube.py's _parse_video_feed / _parse_channel_page)."""
    match = _YT_INITIAL_DATA_RE.search(html)
    if not match:
        return []
    try:
        data = json.loads(match.group(1))
    except json.JSONDecodeError:
        return []

    results: list[dict] = []
    _walk(data, results, limit)
    return results[:limit]


def _walk(node, results: list[dict], limit: int) -> None:
    if len(results) >= limit:
        return
    if isinstance(node, dict):
        video_renderer = node.get("videoRenderer")
        if isinstance(video_renderer, dict):
            parsed = _parse_video_renderer(video_renderer)
            if parsed:
                results.append(parsed)
        for value in node.values():
            if len(results) >= limit:
                return
            _walk(value, results, limit)
    elif isinstance(node, list):
        for value in node:
            if len(results) >= limit:
                return
            _walk(value, results, limit)


def _parse_video_renderer(video_renderer: dict) -> dict | None:
    try:
        video_id = video_renderer["videoId"]
        title = video_renderer["title"]["runs"][0]["text"]
    except (KeyError, IndexError, TypeError):
        return None
    channel = None
    owner_runs = (video_renderer.get("ownerText") or {}).get("runs") or []
    if owner_runs:
        channel = owner_runs[0].get("text")
    views = (video_renderer.get("viewCountText") or {}).get("simpleText")
    return {
        "video_id": video_id,
        "title": title,
        "channel": channel,
        "views": views,
        "url": f"https://www.youtube.com/watch?v={video_id}",
    }
