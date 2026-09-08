from sqlalchemy import select

from app.domain.creator.models import Creator
from app.infrastructure.db.session import AsyncSessionLocal


async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "yara@example.com", "name": "Yara", "niche": "personal finance"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == body["id"]))
        user_id = result.scalar_one().user_id
    return body["id"], user_id


async def test_ingest_and_list_audience_signals(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(
        f"/creators/{creator_id}/audience-signals",
        json={"text": "How do I start budgeting on a tight income?", "source_platform": "instagram"},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["text"].startswith("How do I start")

    resp = await client.get(f"/creators/{creator_id}/audience-signals", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 1


async def test_audience_signals_enforce_tenant_isolation(client):
    creator_id, _ = await _create_creator_and_get_user_id(client, email="zane@example.com", name="Zane")
    resp = await client.get(
        f"/creators/{creator_id}/audience-signals", headers={"X-Debug-User-Id": "usr_someone_else"}
    )
    assert resp.status_code == 404


async def test_analyze_without_signals_is_a_noop(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="amir@example.com", name="Amir")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(f"/creators/{creator_id}/audience/analyze", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["audience"] is None
    assert body["segments"] == []
    assert any("no audience signal" in w.lower() for w in body["warnings"])


async def test_analyze_in_stub_mode_skips_rather_than_guesses(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="bela@example.com", name="Bela")
    headers = {"X-Debug-User-Id": user_id}

    await client.post(
        f"/creators/{creator_id}/audience-signals",
        json={"text": "I never know where my paycheck goes."},
        headers=headers,
    )

    resp = await client.post(f"/creators/{creator_id}/audience/analyze", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["audience"] is None
    assert any("skipped" in w.lower() or "not configured" in w.lower() for w in body["warnings"])


async def test_analyze_enforces_tenant_isolation(client):
    creator_id, _ = await _create_creator_and_get_user_id(client, email="cleo@example.com", name="Cleo")
    resp = await client.post(
        f"/creators/{creator_id}/audience/analyze", headers={"X-Debug-User-Id": "usr_someone_else"}
    )
    assert resp.status_code == 404


async def test_audience_segments_appear_in_state_snapshot_field(client):
    """The field exists and defaults to empty even with nothing inferred yet
    — a regression guard for the CreatorStateSnapshot schema change."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="dax@example.com", name="Dax")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.get(f"/creators/{creator_id}/state", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["audience_segments"] == []
