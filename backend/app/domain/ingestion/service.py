"""Platform ingestion writes (CLAUDE.md §8.3-style discipline: the fetcher
in youtube.py only talks to the network, this module is the only thing that
turns what it returns into rows). Entry point into Creator DNA build
(CLAUDE.md §33 Phase 1->2): a creator pastes a channel link, we go get their
recent content instead of asking them to describe it by hand.
"""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.ids import generate_id
from app.domain.content.models import ContentItem
from app.domain.creator.models import SocialAccount
from app.domain.ingestion.youtube import fetch_recent_videos, fetch_transcript, resolve_channel
from app.domain.memory.service import store_embedding

logger = logging.getLogger(__name__)

MAX_VIDEOS_PER_IMPORT = 15
# Fetching transcripts is the slow part (one network round-trip per video);
# bounded independently of MAX_VIDEOS_PER_IMPORT so ingestion still returns
# in a reasonable time for onboarding even though we still record all the
# lightweight metadata for every fetched video.
MAX_TRANSCRIPTS_PER_IMPORT = 8


async def _get_or_create_social_account(
    db: AsyncSession, *, creator_id: str, channel_id: str, display_name: str, url: str
) -> SocialAccount:
    result = await db.execute(
        select(SocialAccount).where(
            SocialAccount.creator_id == creator_id,
            SocialAccount.platform == "youtube",
            SocialAccount.external_account_id == channel_id,
        )
    )
    account = result.scalar_one_or_none()
    if account is None:
        account = SocialAccount(
            id=generate_id("social_account"),
            creator_id=creator_id,
            platform="youtube",
            external_account_id=channel_id,
            display_name=display_name,
            url=url,
            status="connected",
        )
        db.add(account)
    else:
        account.display_name = display_name
        account.url = url
        account.status = "connected"
    account.last_synced_at = datetime.now(timezone.utc)
    await db.flush()
    return account


def _parse_published_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def import_youtube_channel(db: AsyncSession, *, creator_id: str, url: str) -> dict:
    """Resolves the given URL to a channel, pulls its recent videos, and
    upserts each as a ContentItem (source_type="ingested") — with a best-
    effort transcript on the most recent few, which is what actually feeds
    voice analysis (build_voice_analysis_transcripts only looks at items
    with a transcript). Returns a summary dict rather than raising on
    partial failure (CLAUDE.md §43): a channel with no public captions on
    any video is still a successful import of titles/descriptions.
    """
    channel_id, display_name = await resolve_channel(url)
    account = await _get_or_create_social_account(
        db, creator_id=creator_id, channel_id=channel_id, display_name=display_name, url=url
    )

    videos = await fetch_recent_videos(channel_id, limit=MAX_VIDEOS_PER_IMPORT)
    if not videos:
        return {
            "channel_name": display_name,
            "social_account_id": account.id,
            "imported_count": 0,
            "transcript_count": 0,
            "warnings": ["No public videos were found on this channel's feed."],
        }

    existing_result = await db.execute(
        select(ContentItem).where(ContentItem.creator_id == creator_id, ContentItem.external_id.in_([v["video_id"] for v in videos]))
    )
    existing_by_external_id = {item.external_id: item for item in existing_result.scalars().all()}

    imported_count = 0
    transcript_count = 0
    for index, video in enumerate(videos):
        transcript = fetch_transcript(video["video_id"]) if index < MAX_TRANSCRIPTS_PER_IMPORT else None

        item = existing_by_external_id.get(video["video_id"])
        if item is None:
            item = ContentItem(
                id=generate_id("content_item"),
                creator_id=creator_id,
                title=video["title"],
                platform="youtube",
                format=video["format"],
                status="PUBLISHED",
                source_type="ingested",
                topic=None,
                external_id=video["video_id"],
                external_url=video["url"],
            )
            db.add(item)
        else:
            item.title = video["title"]
            item.format = video["format"]

        if transcript:
            item.transcript = transcript
        await db.flush()
        imported_count += 1

        embed_source_text = transcript or "\n".join(filter(None, [video["title"], video["description"]]))
        if embed_source_text:
            await store_embedding(
                db,
                creator_id=creator_id,
                content_item_id=item.id,
                source_type="transcript" if transcript else "script",
                text=embed_source_text,
            )
        if transcript:
            transcript_count += 1

    warnings = []
    if transcript_count == 0:
        warnings.append(
            "No transcripts were available on the fetched videos (captions may be disabled) — "
            "Creator DNA will be built from titles/descriptions only until a video with captions is imported."
        )

    return {
        "channel_name": display_name,
        "social_account_id": account.id,
        "imported_count": imported_count,
        "transcript_count": transcript_count,
        "warnings": warnings,
    }
