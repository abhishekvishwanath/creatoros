from sqlalchemy import select

from app.domain.creator.models import Creator
from app.domain.research.models import ResearchSource
from app.infrastructure.db.session import AsyncSessionLocal


async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "kim@example.com", "name": "Kim"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == body["id"]))
        user_id = result.scalar_one().user_id
    return body["id"], user_id


async def test_ingest_signal_creates_a_source_when_given_one(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(
        f"/creators/{creator_id}/research-signals",
        json={
            "topic": "budgeting apps",
            "subtopic": "envelope method",
            "format": "short-form video",
            "summary": "A competitor's video on envelope budgeting got unusually high saves.",
            "platform": "instagram",
            "source_url": "https://instagram.com/p/example",
            "source_title": "Envelope budgeting reel",
        },
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["topic"] == "budgeting apps"
    assert body["content_features"]["summary"].startswith("A competitor's video")
    assert body["source_id"] is not None

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ResearchSource).where(ResearchSource.id == body["source_id"]))
        source = result.scalar_one()
    assert source.platform == "instagram"
    assert source.source_type == "creator_provided"


async def test_ingest_signal_without_source_details_has_no_source(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="leo@example.com", name="Leo")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(
        f"/creators/{creator_id}/research-signals",
        json={"topic": "freelance taxes", "summary": "Several people asking about quarterly taxes."},
        headers=headers,
    )
    assert resp.status_code == 201
    assert resp.json()["source_id"] is None


async def test_list_signals_and_state_snapshot_reflects_them(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="mona@example.com", name="Mona")
    headers = {"X-Debug-User-Id": user_id}

    await client.post(
        f"/creators/{creator_id}/research-signals",
        json={"topic": "topic a", "summary": "s"},
        headers=headers,
    )
    await client.post(
        f"/creators/{creator_id}/research-signals",
        json={"topic": "topic b", "summary": "s"},
        headers=headers,
    )

    resp = await client.get(f"/creators/{creator_id}/research-signals", headers=headers)
    assert resp.status_code == 200
    assert len(resp.json()) == 2

    state_resp = await client.get(f"/creators/{creator_id}/state", headers=headers)
    assert len(state_resp.json()["current_research_signals"]) == 2


async def test_research_signals_enforce_tenant_isolation(client):
    creator_id, _ = await _create_creator_and_get_user_id(client, email="nina@example.com", name="Nina")
    resp = await client.get(
        f"/creators/{creator_id}/research-signals", headers={"X-Debug-User-Id": "usr_someone_else"}
    )
    assert resp.status_code == 404
