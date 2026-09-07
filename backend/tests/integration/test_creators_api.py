import pytest


async def _create_creator(client, email="alice@example.com", name="Alice"):
    resp = await client.post("/creators", json={"email": email, "name": name, "niche": "AI"})
    assert resp.status_code == 201
    return resp.json()


async def test_create_creator(client):
    body = await _create_creator(client)
    assert body["id"].startswith("cr_")
    assert body["name"] == "Alice"
    assert body["onboarding_status"] == "created"


async def test_get_creator_requires_auth_header(client):
    creator = await _create_creator(client)
    resp = await client.get(f"/creators/{creator['id']}")
    assert resp.status_code == 401


async def test_get_creator_enforces_tenant_isolation(client):
    """A user id that doesn't own the creator must get a 404, not the data
    (CLAUDE.md 3.1, 46: never expose one creator's data to another user)."""
    creator = await _create_creator(client)
    resp = await client.get(
        f"/creators/{creator['id']}", headers={"X-Debug-User-Id": "usr_someone_else"}
    )
    assert resp.status_code == 404


async def test_get_creator_succeeds_for_owner(client):
    creator = await _create_creator(client)

    # Discover the owning user id via the DB, same as a real client would learn
    # it from Supabase auth once that's wired up (see app/api/deps.py TODO).
    from sqlalchemy import select

    from app.domain.creator.models import Creator
    from app.infrastructure.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == creator["id"]))
        user_id = result.scalar_one().user_id

    resp = await client.get(f"/creators/{creator['id']}", headers={"X-Debug-User-Id": user_id})
    assert resp.status_code == 200
    assert resp.json()["id"] == creator["id"]


async def test_creator_state_snapshot_shape(client):
    from sqlalchemy import select

    from app.domain.creator.models import Creator
    from app.infrastructure.db.session import AsyncSessionLocal

    creator = await _create_creator(client)
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == creator["id"]))
        user_id = result.scalar_one().user_id

    resp = await client.get(
        f"/creators/{creator['id']}/state", headers={"X-Debug-User-Id": user_id}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["creator"]["id"] == creator["id"]
    assert body["positioning"] is None
    assert body["active_goals"] == []


async def test_second_creator_belonging_to_different_user_is_isolated(client):
    creator_a = await _create_creator(client, email="a@example.com", name="A")
    creator_b = await _create_creator(client, email="b@example.com", name="B")
    assert creator_a["id"] != creator_b["id"]

    from sqlalchemy import select

    from app.domain.creator.models import Creator
    from app.infrastructure.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == creator_a["id"]))
        user_a_id = result.scalar_one().user_id

    # user_a must not be able to read creator_b's data
    resp = await client.get(f"/creators/{creator_b['id']}", headers={"X-Debug-User-Id": user_a_id})
    assert resp.status_code == 404
