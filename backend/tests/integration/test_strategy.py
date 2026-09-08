from sqlalchemy import select

from app.domain.creator.models import Creator
from app.domain.research.models import Opportunity
from app.domain.strategy.service import apply_strategy
from app.infrastructure.db.session import AsyncSessionLocal


async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "sam@example.com", "name": "Sam", "niche": "personal finance"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == body["id"]))
        user_id = result.scalar_one().user_id
    return body["id"], user_id


async def _add_approved_opportunity(creator_id: str, opp_id: str = "opp_seed") -> None:
    async with AsyncSessionLocal() as session:
        session.add(Opportunity(id=opp_id, creator_id=creator_id, topic="budgeting", status="approved"))
        await session.commit()


async def test_generate_without_opportunities_is_a_noop(client):
    """No approved/saved opportunities exist yet — must return an honest
    empty result with a warning, not an error."""
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(f"/creators/{creator_id}/strategy/generate", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["strategy"] is None
    assert any("no approved or saved" in w.lower() for w in body["warnings"])


async def test_generate_in_stub_mode_skips_rather_than_guesses(client):
    """With an opportunity available but no model provider configured,
    portfolio balancing has no honest rule-based fallback — it must skip."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="tara@example.com", name="Tara")
    headers = {"X-Debug-User-Id": user_id}
    await _add_approved_opportunity(creator_id)

    resp = await client.post(f"/creators/{creator_id}/strategy/generate", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["strategy"] is None
    assert any("skipped" in w.lower() or "not configured" in w.lower() for w in body["warnings"])


async def test_list_strategies_enforces_tenant_isolation(client):
    creator_id, _ = await _create_creator_and_get_user_id(client, email="uma@example.com", name="Uma")
    resp = await client.get(f"/creators/{creator_id}/strategy", headers={"X-Debug-User-Id": "usr_someone_else"})
    assert resp.status_code == 404


async def test_patch_unknown_strategy_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="vik@example.com", name="Vik")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.patch(
        f"/creators/{creator_id}/strategy/strat_does_not_exist",
        json={"status": "active"},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_patch_strategy_enforces_tenant_isolation(client):
    """A strategy created (via the domain service directly, since stub mode
    can't generate one through the API) under creator A must 404 when a
    different creator's owner tries to patch it — not just "unknown id"."""
    owner_creator_id, owner_user_id = await _create_creator_and_get_user_id(client, email="wes@example.com", name="Wes")
    other_creator_id, other_user_id = await _create_creator_and_get_user_id(
        client, email="xena@example.com", name="Xena"
    )

    async with AsyncSessionLocal() as session:
        strategy = await apply_strategy(
            session, creator_id=owner_creator_id, summary="s", confidence=0.5, items=[]
        )
        await session.commit()
        strategy_id = strategy.id

    resp = await client.patch(
        f"/creators/{other_creator_id}/strategy/{strategy_id}",
        json={"status": "active"},
        headers={"X-Debug-User-Id": other_user_id},
    )
    assert resp.status_code == 404

    resp = await client.patch(
        f"/creators/{owner_creator_id}/strategy/{strategy_id}",
        json={"status": "active"},
        headers={"X-Debug-User-Id": owner_user_id},
    )
    assert resp.status_code == 200
