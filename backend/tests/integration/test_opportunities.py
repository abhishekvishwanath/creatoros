from sqlalchemy import select

from app.domain.creator.models import Creator
from app.infrastructure.db.session import AsyncSessionLocal


async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "oscar@example.com", "name": "Oscar", "niche": "personal finance"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == body["id"]))
        user_id = result.scalar_one().user_id
    return body["id"], user_id


async def test_generate_without_signals_is_a_noop(client):
    """No ANTHROPIC_API_KEY/GROQ_API_KEY in the test environment, and there
    are no research signals ingested either — this must return an honest
    empty result with a warning, not an error, and not a fabricated list."""
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(f"/creators/{creator_id}/opportunities/generate", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["opportunities"] == []
    assert any("no research signal" in w.lower() for w in body["warnings"])


async def test_generate_in_stub_mode_skips_rather_than_guesses(client):
    """With signals present but no model provider configured, opportunity
    scoring has no honest rule-based fallback (unlike positioning) — it must
    skip, not fabricate opportunities."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="pat@example.com", name="Pat")
    headers = {"X-Debug-User-Id": user_id}

    await client.post(
        f"/creators/{creator_id}/research-signals",
        json={"topic": "budgeting", "summary": "A trend about zero-based budgeting."},
        headers=headers,
    )

    resp = await client.post(f"/creators/{creator_id}/opportunities/generate", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["opportunities"] == []
    assert any("no model provider" in w.lower() or "not configured" in w.lower() or "skipped" in w.lower() for w in [w.lower() for w in body["warnings"]])


async def test_list_opportunities_enforces_tenant_isolation(client):
    creator_id, _ = await _create_creator_and_get_user_id(client, email="quinn@example.com", name="Quinn")
    resp = await client.get(
        f"/creators/{creator_id}/opportunities", headers={"X-Debug-User-Id": "usr_someone_else"}
    )
    assert resp.status_code == 404


async def test_patch_unknown_opportunity_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="ray@example.com", name="Ray")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.patch(
        f"/creators/{creator_id}/opportunities/opp_does_not_exist",
        json={"status": "approved"},
        headers=headers,
    )
    assert resp.status_code == 404
