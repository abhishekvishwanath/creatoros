from datetime import datetime, timedelta, timezone

import jwt
from sqlalchemy import select

from app.api import deps as deps_module
from app.api.routes import creators as creators_module
from app.domain.creator.models import Creator
from app.infrastructure.db.session import AsyncSessionLocal

SECRET = "integration-test-secret"


class _FakeSettings:
    supabase_url = "https://example.supabase.co"
    supabase_jwt_secret = SECRET


def _enable_fake_jwt_secret(monkeypatch):
    """Both app/api/deps.py and app/api/routes/creators.py import
    get_settings into their own module namespace, so both need patching for
    a consistent view of "real auth is configured" across the whole request."""
    monkeypatch.setattr(deps_module, "get_settings", lambda: _FakeSettings())
    monkeypatch.setattr(creators_module, "get_settings", lambda: _FakeSettings())


def _make_token(*, sub: str, email: str) -> str:
    return jwt.encode(
        {"sub": sub, "email": email, "aud": "authenticated", "exp": datetime.now(timezone.utc) + timedelta(hours=1)},
        SECRET,
        algorithm="HS256",
    )


async def test_bearer_token_creates_creator_and_provisions_user(client, monkeypatch):
    _enable_fake_jwt_secret(monkeypatch)
    token = _make_token(sub="auth_creator_1", email="creator1@example.com")

    resp = await client.post(
        "/creators", json={"name": "JWT Creator"}, headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "JWT Creator"

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == body["id"]))
        creator = result.scalar_one()
    assert creator.user_id == body["user_id"]


async def test_bearer_token_reuses_the_same_user_across_requests(client, monkeypatch):
    _enable_fake_jwt_secret(monkeypatch)
    token = _make_token(sub="auth_creator_2", email="creator2@example.com")
    headers = {"Authorization": f"Bearer {token}"}

    first = await client.post("/creators", json={"name": "First"}, headers=headers)
    second = await client.post("/creators", json={"name": "Second"}, headers=headers)
    assert first.json()["user_id"] == second.json()["user_id"]

    mine = await client.get("/creators", headers=headers)
    assert mine.status_code == 200
    names = {c["name"] for c in mine.json()}
    assert names == {"First", "Second"}


async def test_invalid_bearer_token_is_rejected(client, monkeypatch):
    _enable_fake_jwt_secret(monkeypatch)
    resp = await client.post(
        "/creators", json={"name": "Nope"}, headers={"Authorization": "Bearer not-a-real-token"}
    )
    assert resp.status_code == 401


async def test_debug_header_is_rejected_once_real_auth_is_configured(client, monkeypatch):
    _enable_fake_jwt_secret(monkeypatch)
    resp = await client.get("/creators", headers={"X-Debug-User-Id": "usr_whatever"})
    assert resp.status_code == 401


async def test_email_bootstrap_fallback_is_disabled_once_real_auth_is_configured(client, monkeypatch):
    _enable_fake_jwt_secret(monkeypatch)
    resp = await client.post("/creators", json={"name": "Should fail", "email": "shouldfail@example.com"})
    assert resp.status_code == 401


async def test_missing_credentials_is_401(client):
    resp = await client.get("/creators")
    assert resp.status_code == 401


async def test_list_my_creators_empty_for_new_debug_user(client):
    resp = await client.post("/creators", json={"email": "listmine@example.com", "name": "List Mine"})
    assert resp.status_code == 201
    user_id = resp.json()["user_id"]

    mine = await client.get("/creators", headers={"X-Debug-User-Id": user_id})
    assert mine.status_code == 200
    assert len(mine.json()) == 1
    assert mine.json()[0]["name"] == "List Mine"
