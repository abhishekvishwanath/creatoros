from datetime import datetime, timezone

from sqlalchemy import select

from app.core.ids import generate_id
from app.domain.content.models import ContentItem
from app.domain.creator.models import Creator
from app.domain.performance.models import PerformanceSnapshot
from app.infrastructure.db.session import AsyncSessionLocal

POSITIVE_FACTOR = [{"factor": "Contrarian hook", "confidence": "medium", "note": "n"}]


async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "learn-route@example.com", "name": "Learn", "niche": "cooking"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == body["id"]))
        user_id = result.scalar_one().user_id
    return body["id"], user_id


async def _add_diagnosed_snapshot(creator_id: str, item_id: str, *, ratio: float = 1.6) -> None:
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id=item_id, creator_id=creator_id, topic="t", format="short", status="PUBLISHED"))
        session.add(
            PerformanceSnapshot(
                id=generate_id("performance_snapshot"),
                creator_id=creator_id,
                content_item_id=item_id,
                views=1000,
                captured_at=datetime.now(timezone.utc),
                baseline_comparison={
                    "views_vs_overall_median": ratio,
                    "diagnosis": {"summary": "s", "associated_factors": POSITIVE_FACTOR, "confidence": "medium"},
                },
            )
        )
        await session.commit()


async def test_sync_then_list_learnings(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}
    await _add_diagnosed_snapshot(creator_id, "cnt_lroute1", ratio=1.6)
    await _add_diagnosed_snapshot(creator_id, "cnt_lroute2", ratio=1.8)

    sync_resp = await client.post(f"/creators/{creator_id}/learnings/sync", headers=headers)
    assert sync_resp.status_code == 200
    synced = sync_resp.json()
    assert len(synced) == 1
    assert "contrarian hook" in synced[0]["statement"].lower()

    list_resp = await client.get(f"/creators/{creator_id}/learnings", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_sync_with_insufficient_evidence_returns_empty(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="learn-route8@example.com", name="Learn8")
    headers = {"X-Debug-User-Id": user_id}
    await _add_diagnosed_snapshot(creator_id, "cnt_lroute9", ratio=1.6)

    resp = await client.post(f"/creators/{creator_id}/learnings/sync", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_list_learnings_before_sync_is_empty(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="learn-route2@example.com", name="Learn2")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.get(f"/creators/{creator_id}/learnings", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_retract_learning(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="learn-route3@example.com", name="Learn3")
    headers = {"X-Debug-User-Id": user_id}
    await _add_diagnosed_snapshot(creator_id, "cnt_lroute3", ratio=1.6)
    await _add_diagnosed_snapshot(creator_id, "cnt_lroute4", ratio=1.8)
    sync_resp = await client.post(f"/creators/{creator_id}/learnings/sync", headers=headers)
    learning_id = sync_resp.json()[0]["id"]

    patch_resp = await client.patch(
        f"/creators/{creator_id}/learnings/{learning_id}", json={"status": "retracted"}, headers=headers
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["status"] == "retracted"

    list_resp = await client.get(f"/creators/{creator_id}/learnings", headers=headers)
    assert list_resp.json() == []

    list_all_resp = await client.get(f"/creators/{creator_id}/learnings?status=retracted", headers=headers)
    assert len(list_all_resp.json()) == 1


async def test_retract_with_invalid_status_is_422(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="learn-route9@example.com", name="Learn9")
    headers = {"X-Debug-User-Id": user_id}
    await _add_diagnosed_snapshot(creator_id, "cnt_lroute10", ratio=1.6)
    await _add_diagnosed_snapshot(creator_id, "cnt_lroute11", ratio=1.8)
    sync_resp = await client.post(f"/creators/{creator_id}/learnings/sync", headers=headers)
    learning_id = sync_resp.json()[0]["id"]

    resp = await client.patch(
        f"/creators/{creator_id}/learnings/{learning_id}", json={"status": "not-a-real-status"}, headers=headers
    )
    assert resp.status_code == 422


async def test_resync_does_not_resurrect_a_retracted_learning(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="learn-route10@example.com", name="Learn10")
    headers = {"X-Debug-User-Id": user_id}
    await _add_diagnosed_snapshot(creator_id, "cnt_lroute12", ratio=1.6)
    await _add_diagnosed_snapshot(creator_id, "cnt_lroute13", ratio=1.8)
    sync_resp = await client.post(f"/creators/{creator_id}/learnings/sync", headers=headers)
    learning_id = sync_resp.json()[0]["id"]
    await client.patch(f"/creators/{creator_id}/learnings/{learning_id}", json={"status": "retracted"}, headers=headers)

    await _add_diagnosed_snapshot(creator_id, "cnt_lroute14", ratio=1.7)
    resync_resp = await client.post(f"/creators/{creator_id}/learnings/sync", headers=headers)
    assert resync_resp.json() == []

    active_resp = await client.get(f"/creators/{creator_id}/learnings", headers=headers)
    assert active_resp.json() == []


async def test_retract_unknown_learning_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="learn-route4@example.com", name="Learn4")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.patch(
        f"/creators/{creator_id}/learnings/missing", json={"status": "retracted"}, headers=headers
    )
    assert resp.status_code == 404


async def test_learnings_are_scoped_to_the_owning_creator(client):
    creator_a, user_a = await _create_creator_and_get_user_id(client, email="learn-route5@example.com", name="A")
    creator_b, user_b = await _create_creator_and_get_user_id(client, email="learn-route6@example.com", name="B")
    await _add_diagnosed_snapshot(creator_a, "cnt_lroute5", ratio=1.6)
    await _add_diagnosed_snapshot(creator_a, "cnt_lroute6", ratio=1.8)

    resp = await client.get(f"/creators/{creator_a}/learnings", headers={"X-Debug-User-Id": user_b})
    assert resp.status_code == 404


async def test_creator_state_snapshot_includes_active_learnings(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="learn-route7@example.com", name="C7")
    headers = {"X-Debug-User-Id": user_id}
    await _add_diagnosed_snapshot(creator_id, "cnt_lroute7", ratio=1.6)
    await _add_diagnosed_snapshot(creator_id, "cnt_lroute8", ratio=1.8)
    await client.post(f"/creators/{creator_id}/learnings/sync", headers=headers)

    state_resp = await client.get(f"/creators/{creator_id}/state", headers=headers)
    assert state_resp.status_code == 200
    learnings = state_resp.json()["strategic_learnings"]
    assert len(learnings) == 1
    assert "contrarian hook" in learnings[0]["statement"].lower()
