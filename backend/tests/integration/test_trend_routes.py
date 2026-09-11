from sqlalchemy import select

from app.domain.creator.models import Creator
from app.infrastructure.db.session import AsyncSessionLocal


async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "trendroute@example.com", "name": "Trend Route Creator"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == body["id"]))
        user_id = result.scalar_one().user_id
    return body["id"], user_id


async def test_trends_empty_initially(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    resp = await client.get(f"/creators/{creator_id}/research/trends", headers={"X-Debug-User-Id": user_id})
    assert resp.status_code == 200
    assert resp.json() == []


async def test_analyze_trends_with_no_signals_skips_gracefully(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="trendroute2@example.com", name="Trend2")
    headers = {"X-Debug-User-Id": user_id}
    resp = await client.post(f"/creators/{creator_id}/research/trends/analyze", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["insights"] == []
    assert any("signal" in w.lower() for w in body["warnings"])


async def test_analyze_trends_in_stub_mode_skips_rather_than_guesses(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="trendroute3@example.com", name="Trend3")
    headers = {"X-Debug-User-Id": user_id}

    signal_resp = await client.post(
        f"/creators/{creator_id}/research-signals",
        json={"topic": "AI productivity", "summary": "A competitor's AI workflow video got unusually high saves."},
        headers=headers,
    )
    assert signal_resp.status_code == 201

    resp = await client.post(f"/creators/{creator_id}/research/trends/analyze", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["insights"] == []
    assert any("skipped" in w.lower() or "not configured" in w.lower() for w in body["warnings"])

    list_resp = await client.get(f"/creators/{creator_id}/research/trends", headers=headers)
    assert list_resp.json() == []


async def test_trends_enforce_tenant_isolation(client):
    creator_id, _ = await _create_creator_and_get_user_id(client, email="trendroute4@example.com", name="Trend4")
    resp = await client.get(f"/creators/{creator_id}/research/trends", headers={"X-Debug-User-Id": "usr_someone_else"})
    assert resp.status_code == 404
