from sqlalchemy import select

from app.domain.creator.models import Creator
from app.infrastructure.db.session import AsyncSessionLocal


async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "eve@example.com", "name": "Eve"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == body["id"]))
        user_id = result.scalar_one().user_id
    return body["id"], user_id


async def test_ingest_and_list_content(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(
        f"/creators/{creator_id}/content",
        json={"title": "My best Reel", "platform": "instagram", "format": "short", "transcript": "hook... body... cta"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "PUBLISHED"
    assert body["source_type"] == "ingested"

    resp = await client.get(f"/creators/{creator_id}/content", headers=headers)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 1
    assert items[0]["title"] == "My best Reel"


async def test_content_list_enforces_tenant_isolation(client):
    creator_id, _ = await _create_creator_and_get_user_id(client, email="frank@example.com", name="Frank")
    resp = await client.get(
        f"/creators/{creator_id}/content", headers={"X-Debug-User-Id": "usr_someone_else"}
    )
    assert resp.status_code == 404


async def test_content_appears_in_creator_state_snapshot(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="gina@example.com", name="Gina")
    headers = {"X-Debug-User-Id": user_id}

    await client.post(
        f"/creators/{creator_id}/content",
        json={"title": "Launch video", "platform": "youtube", "transcript": "transcript text"},
        headers=headers,
    )

    resp = await client.get(f"/creators/{creator_id}/state", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["recent_content"]) == 1
    assert body["recent_content"][0]["title"] == "Launch video"
    assert body["recent_content"][0]["has_transcript"] is True
