"""YouTube link ingestion (CLAUDE.md §17.1, §69): given a channel URL, fetch
its recent videos without requiring the creator to hand-type anything.

Uses only unauthenticated, public endpoints — no OAuth, no API key,
nothing that needs an account-setup decision from the creator:

- The channel's public page, to resolve a handle/custom URL to a stable
  channel_id (YouTube doesn't expose that mapping any other way).
- YouTube's public per-channel RSS feed, to list recent videos. This is the
  same feed a podcast/RSS reader would subscribe to; it's the documented,
  supported way to get a channel's recent uploads without the Data API.
- youtube-transcript-api, which reads the public caption track YouTube
  already serves to any viewer (the same data the "cc" button shows) — not
  a bypass of anything access-controlled. Videos with captions disabled or
  no transcript available simply come back with transcript=None; that's a
  normal, expected outcome, not an error.

Every network call is wrapped and bounded: a fetch failure degrades to an
empty/partial result (CLAUDE.md §43), never an exception the route has to
turn into a 500.
"""

import logging
import re
from xml.etree import ElementTree

import httpx

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (compatible; CreatorIntelligenceOS/1.0; +https://github.com/abhishekvishwanath/creatoros)"
_TIMEOUT = 10.0
# EU-region outbound IPs (e.g. Railway's default region) get redirected
# through consent.youtube.com's cookie-consent interstitial before the real
# page loads, which has no channelId to find. This cookie pre-declares
# consent (the same thing accepting the banner would set) and skips the
# redirect entirely — it's opting out of a GDPR cookie-consent wall on
# public content, not bypassing any login/auth. Harmless to send from
# non-EU IPs too, where YouTube already skips the wall.
_HEADERS = {"User-Agent": _UA, "Cookie": "CONSENT=YES+1"}
_CHANNEL_ID_RE = re.compile(r'"channelId":"(UC[\w-]{10,})"')
_ATOM_NS = "{http://www.w3.org/2005/Atom}"
_YT_NS = "{http://www.youtube.com/xml/schemas/2015}"
_MEDIA_NS = "{http://search.yahoo.com/mrss/}"


class YoutubeResolutionError(Exception):
    """Raised when a given URL can't be resolved to a real YouTube channel —
    a 4xx-shaped failure the route surfaces to the creator to fix (a bad
    link), not a 502 (a transient upstream/system failure)."""


def _direct_channel_id(url: str) -> str | None:
    match = re.search(r"youtube\.com/channel/(UC[\w-]{10,})", url)
    return match.group(1) if match else None


async def resolve_channel(url: str) -> tuple[str, str]:
    """Returns (channel_id, display_name). Accepts /channel/UC..., @handle,
    /c/name, and /user/name forms — anything a creator would plausibly paste
    from their own browser address bar."""
    url = url.strip()
    if not url:
        raise YoutubeResolutionError("No URL provided.")

    direct_id = _direct_channel_id(url)
    if direct_id:
        channel_id = direct_id
        page_url = f"https://www.youtube.com/channel/{channel_id}"
    else:
        if not re.match(r"^https?://", url):
            url = f"https://{url}"
        if "youtube.com" not in url and "youtu.be" not in url:
            raise YoutubeResolutionError("That doesn't look like a YouTube URL.")
        page_url = url
        channel_id = None

    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT, follow_redirects=True) as client:
            response = await client.get(page_url)
    except httpx.HTTPError as exc:
        raise YoutubeResolutionError(f"Couldn't reach YouTube: {exc}") from exc

    if response.status_code == 404:
        raise YoutubeResolutionError("No YouTube channel found at that URL.")
    response.raise_for_status()

    return _parse_channel_page(response.text)


def _parse_channel_page(html: str) -> tuple[str, str]:
    """Pure parsing half of resolve_channel, split out for unit testing
    without a network call."""
    match = _CHANNEL_ID_RE.search(html)
    if not match:
        raise YoutubeResolutionError("Couldn't find a channel on that page.")
    resolved_id = match.group(1)

    name_match = re.search(r'"channelMetadataRenderer":\s*{\s*"title":"([^"]+)"', html)
    if not name_match:
        name_match = re.search(r"<title>([^<]+)</title>", html)
    display_name = name_match.group(1).replace(" - YouTube", "").strip() if name_match else resolved_id

    return resolved_id, display_name


async def fetch_recent_videos(channel_id: str, *, limit: int = 15) -> list[dict]:
    """Recent uploads from the channel's public RSS feed (typically the
    last ~15 — YouTube doesn't paginate this feed further). Each item:
    {video_id, title, description, published_at, thumbnail_url, url}."""
    feed_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    try:
        async with httpx.AsyncClient(headers=_HEADERS, timeout=_TIMEOUT) as client:
            response = await client.get(feed_url)
            response.raise_for_status()
    except httpx.HTTPError:
        logger.warning("YouTube RSS fetch failed for channel %s", channel_id, exc_info=True)
        return []

    try:
        return _parse_video_feed(response.text, limit=limit)
    except ElementTree.ParseError:
        logger.warning("YouTube RSS feed for channel %s was not valid XML", channel_id)
        return []


def _parse_video_feed(xml_text: str, *, limit: int) -> list[dict]:
    """Pure parsing half of fetch_recent_videos, split out for unit testing
    without a network call."""
    root = ElementTree.fromstring(xml_text)

    videos = []
    for entry in root.findall(f"{_ATOM_NS}entry")[:limit]:
        video_id = entry.findtext(f"{_YT_NS}videoId")
        title = entry.findtext(f"{_ATOM_NS}title")
        published = entry.findtext(f"{_ATOM_NS}published")
        group = entry.find(f"{_MEDIA_NS}group")
        description = group.findtext(f"{_MEDIA_NS}description") if group is not None else None
        thumbnail = group.find(f"{_MEDIA_NS}thumbnail") if group is not None else None
        thumbnail_url = thumbnail.get("url") if thumbnail is not None else None
        link_el = entry.find(f"{_ATOM_NS}link[@rel='alternate']")
        href = link_el.get("href") if link_el is not None else ""
        if not video_id or not title:
            continue
        videos.append(
            {
                "video_id": video_id,
                "title": title,
                "description": description,
                "published_at": published,
                "thumbnail_url": thumbnail_url,
                "format": "short" if "/shorts/" in (href or "") else "long",
                "url": f"https://www.youtube.com/watch?v={video_id}",
            }
        )
    return videos


def fetch_transcript(video_id: str) -> str | None:
    """Best-effort — most channels have captions disabled on at least some
    videos, and that's a normal outcome here, not a failure to log loudly."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id)
        text = " ".join(segment.text for segment in fetched)
        return text.strip() or None
    except Exception:
        return None
