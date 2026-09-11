"""Integration tests for POST /creators/{id}/import/youtube. The actual
network calls (resolve_channel, fetch_recent_videos, fetch_transcript) are
monkeypatched — the automated suite must stay hermetic (see
tests/conftest.py), and youtube.py's own parsing logic is already covered
by tests/unit/test_youtube_ingestion.py."""

from sqlalchemy import select

from app.domain.content.models import ContentEmbedding, ContentItem
from app.domain.creator.models import Creator, SocialAccount
from app.domain.ingestion import service as ingestion_service
from app.infrastructure.db.session import AsyncSessionLocal


async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "importer@example.com", "name": "Importer"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == body["id"]))
        user_id = result.scalar_one().user_id
    return body["id"], user_id


def _patch_youtube(monkeypatch, *, videos, transcripts=None):
    async def fake_resolve_channel(url):
        return "UCfakechannelid1234", "Fake Channel"

    async def fake_fetch_recent_videos(channel_id, *, limit=15):
        return videos

    def fake_fetch_transcript(video_id):
        return (transcripts or {}).get(video_id)

    monkeypatch.setattr(ingestion_service, "resolve_channel", fake_resolve_channel)
    monkeypatch.setattr(ingestion_service, "fetch_recent_videos", fake_fetch_recent_videos)
    monkeypatch.setattr(ingestion_service, "fetch_transcript", fake_fetch_transcript)


_VIDEOS = [
    {
        "video_id": "vid1",
        "title": "Video One",
        "description": "About productivity",
        "published_at": "2026-01-01T00:00:00+00:00",
        "thumbnail_url": "https://example.com/1.jpg",
        "format": "short",
        "url": "https://www.youtube.com/watch?v=vid1",
    },
    {
        "video_id": "vid2",
        "title": "Video Two",
        "description": "About workflows",
        "published_at": "2026-01-02T00:00:00+00:00",
        "thumbnail_url": "https://example.com/2.jpg",
        "format": "long",
        "url": "https://www.youtube.com/watch?v=vid2",
    },
]


async def test_import_creates_content_items_and_social_account(client, monkeypatch):
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}
    _patch_youtube(monkeypatch, videos=_VIDEOS, transcripts={"vid1": "hook body cta transcript text"})

    resp = await client.post(
        f"/creators/{creator_id}/import/youtube", json={"url": "https://youtube.com/@fake"}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["channel_name"] == "Fake Channel"
    assert body["imported_count"] == 2
    assert body["transcript_count"] == 1

    async with AsyncSessionLocal() as session:
        items = (await session.execute(select(ContentItem).where(ContentItem.creator_id == creator_id))).scalars().all()
        accounts = (
            (await session.execute(select(SocialAccount).where(SocialAccount.creator_id == creator_id)))
            .scalars()
            .all()
        )
        embeddings = (
            (await session.execute(select(ContentEmbedding).where(ContentEmbedding.creator_id == creator_id)))
            .scalars()
            .all()
        )
    assert len(items) == 2
    assert {i.external_id for i in items} == {"vid1", "vid2"}
    assert len(accounts) == 1
    assert accounts[0].platform == "youtube"
    assert accounts[0].display_name == "Fake Channel"
    assert len(embeddings) == 2  # one per video, even without a transcript (falls back to title+description)


async def test_reimporting_the_same_channel_does_not_duplicate_content_items(client, monkeypatch):
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}
    _patch_youtube(monkeypatch, videos=_VIDEOS)

    resp1 = await client.post(
        f"/creators/{creator_id}/import/youtube", json={"url": "https://youtube.com/@fake"}, headers=headers
    )
    assert resp1.status_code == 200
    resp2 = await client.post(
        f"/creators/{creator_id}/import/youtube", json={"url": "https://youtube.com/@fake"}, headers=headers
    )
    assert resp2.status_code == 200

    async with AsyncSessionLocal() as session:
        items = (await session.execute(select(ContentItem).where(ContentItem.creator_id == creator_id))).scalars().all()
        accounts = (
            (await session.execute(select(SocialAccount).where(SocialAccount.creator_id == creator_id)))
            .scalars()
            .all()
        )
    assert len(items) == 2  # still 2, not 4
    assert len(accounts) == 1  # still 1, not 2


async def test_import_with_no_videos_returns_a_warning_not_an_error(client, monkeypatch):
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}
    _patch_youtube(monkeypatch, videos=[])

    resp = await client.post(
        f"/creators/{creator_id}/import/youtube", json={"url": "https://youtube.com/@fake"}, headers=headers
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["imported_count"] == 0
    assert body["warnings"]


async def test_import_enforces_tenant_isolation(client):
    creator_id, _ = await _create_creator_and_get_user_id(client, email="owner@example.com", name="Owner")
    resp = await client.post(
        f"/creators/{creator_id}/import/youtube",
        json={"url": "https://youtube.com/@fake"},
        headers={"X-Debug-User-Id": "usr_someone_else"},
    )
    assert resp.status_code == 404


async def test_resolution_failure_returns_422(client, monkeypatch):
    from app.domain.ingestion.youtube import YoutubeResolutionError

    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}

    async def fake_resolve_channel(url):
        raise YoutubeResolutionError("That doesn't look like a YouTube URL.")

    monkeypatch.setattr(ingestion_service, "resolve_channel", fake_resolve_channel)

    resp = await client.post(
        f"/creators/{creator_id}/import/youtube", json={"url": "not a url"}, headers=headers
    )
    assert resp.status_code == 422
