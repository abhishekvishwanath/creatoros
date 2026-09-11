"""Integration tests for the /pipeline/run orchestration endpoint. Network
calls (YouTube import + search) are monkeypatched — model calls run in the
test suite's forced stub mode (see conftest.py), which every stage already
handles gracefully (a stub Creator Intelligence run still produces a
placeholder positioning; Opportunity/Strategy engines return an honest
"skipped, no evidence" result rather than crashing) — this test is about
verifying the orchestration/stage-tracking wiring, not agent output quality
(that's covered by each stage's own existing tests).

The FastAPI BackgroundTask kicked off by POST /pipeline/run is NOT
guaranteed to have finished by the time that request returns, even with
httpx's ASGITransport (empirically: it often hasn't) — so tests poll
GET /pipeline/run/{id} the same way the real frontend does, rather than
assuming synchronous completion.
"""

import asyncio

from sqlalchemy import select

from app.domain.creator.models import Creator
from app.domain.ingestion import service as ingestion_service
from app.domain.pipeline.models import PIPELINE_STAGE_NAMES
from app.domain.research import auto_seed as auto_seed_module
from app.infrastructure.db.session import AsyncSessionLocal

_TERMINAL_STATUSES = ("completed", "failed")


async def _poll_until_terminal(client, creator_id: str, run_id: str, headers: dict, *, max_attempts: int = 50) -> dict:
    for _ in range(max_attempts):
        resp = await client.get(f"/creators/{creator_id}/pipeline/run/{run_id}", headers=headers)
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] in _TERMINAL_STATUSES:
            return body
        await asyncio.sleep(0.1)
    raise AssertionError(f"Pipeline run {run_id} did not reach a terminal status in time: {body}")


async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "pipeline-tester@example.com", "name": "Pipeline Tester", "niche": "tech reviews"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == body["id"]))
        user_id = result.scalar_one().user_id
    return body["id"], user_id


def _patch_youtube_import(monkeypatch):
    async def fake_resolve_channel(url):
        return "UCfakechannelid1234", "Fake Channel"

    async def fake_fetch_recent_videos(channel_id, *, limit=15):
        return [
            {
                "video_id": "vid1",
                "title": "Video One",
                "description": "About tech reviews",
                "published_at": "2026-01-01T00:00:00+00:00",
                "thumbnail_url": None,
                "format": "long",
                "url": "https://www.youtube.com/watch?v=vid1",
            }
        ]

    def fake_fetch_transcript(video_id):
        return None

    monkeypatch.setattr(ingestion_service, "resolve_channel", fake_resolve_channel)
    monkeypatch.setattr(ingestion_service, "fetch_recent_videos", fake_fetch_recent_videos)
    monkeypatch.setattr(ingestion_service, "fetch_transcript", fake_fetch_transcript)


def _patch_youtube_search(monkeypatch):
    async def fake_search_videos(query, *, limit=5):
        return [
            {
                "video_id": "search1",
                "title": f"A real video about {query}",
                "channel": "Some Channel",
                "views": "1,000 views",
                "url": "https://www.youtube.com/watch?v=search1",
            }
        ]

    monkeypatch.setattr(auto_seed_module, "search_videos", fake_search_videos)


async def test_pipeline_run_with_youtube_url_completes_all_stages(client, monkeypatch):
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}
    _patch_youtube_import(monkeypatch)
    _patch_youtube_search(monkeypatch)

    resp = await client.post(f"/creators/{creator_id}/pipeline/run", json={"youtube_url": "https://youtube.com/@fake"}, headers=headers)
    assert resp.status_code == 202
    run_id = resp.json()["id"]

    body = await _poll_until_terminal(client, creator_id, run_id, headers)
    assert body["status"] == "completed"
    stage_names = [s["name"] for s in body["stages"]]
    assert stage_names == PIPELINE_STAGE_NAMES
    import_stage = next(s for s in body["stages"] if s["name"] == "import")
    assert import_stage["status"] == "success"
    assert "Imported 1 video" in import_stage["summary"]
    # Every other stage must reach a terminal state (success or failed, never
    # left "pending"/"running") even though the model itself runs in stub
    # mode for this test.
    for stage in body["stages"][1:]:
        assert stage["status"] in ("success", "failed", "skipped")


async def test_pipeline_run_without_youtube_url_skips_import_stage(client, monkeypatch):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="pipeline-tester2@example.com")
    headers = {"X-Debug-User-Id": user_id}
    _patch_youtube_search(monkeypatch)

    resp = await client.post(f"/creators/{creator_id}/pipeline/run", json={}, headers=headers)
    assert resp.status_code == 202
    run_id = resp.json()["id"]

    body = await _poll_until_terminal(client, creator_id, run_id, headers)
    import_stage = next(s for s in body["stages"] if s["name"] == "import")
    assert import_stage["status"] == "skipped"


async def test_research_stage_produces_real_signals_that_reach_opportunity_engine(client, monkeypatch):
    """The whole point of auto-seeding: Opportunity Engine's context is fed
    with real, non-empty research signals produced earlier in the same run,
    not an empty list (which it would otherwise honestly refuse to score
    against — see opportunity_engine.py's early return)."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="pipeline-tester3@example.com")
    headers = {"X-Debug-User-Id": user_id}
    _patch_youtube_search(monkeypatch)

    resp = await client.post(f"/creators/{creator_id}/pipeline/run", json={}, headers=headers)
    run_id = resp.json()["id"]

    body = await _poll_until_terminal(client, creator_id, run_id, headers)
    research_stage = next(s for s in body["stages"] if s["name"] == "research")
    assert research_stage["status"] == "success"
    assert "1 real research signal" in research_stage["summary"]

    signals_resp = await client.get(f"/creators/{creator_id}/research-signals", headers=headers)
    assert len(signals_resp.json()) == 1


async def test_pipeline_run_enforces_tenant_isolation(client):
    creator_id, _ = await _create_creator_and_get_user_id(client, email="pipeline-owner@example.com")
    resp = await client.post(
        f"/creators/{creator_id}/pipeline/run", json={}, headers={"X-Debug-User-Id": "usr_someone_else"}
    )
    assert resp.status_code == 404


async def test_pipeline_run_status_404_for_unknown_run_id(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="pipeline-tester4@example.com")
    resp = await client.get(f"/creators/{creator_id}/pipeline/run/pline_doesnotexist", headers={"X-Debug-User-Id": user_id})
    assert resp.status_code == 404
