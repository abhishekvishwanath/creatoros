from sqlalchemy import select

from app.domain.content.models import ContentItem
from app.domain.creator.models import Creator
from app.domain.performance.models import PerformanceSnapshot
from app.infrastructure.db.session import AsyncSessionLocal


async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "perf-route@example.com", "name": "Perf", "niche": "cooking"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == body["id"]))
        user_id = result.scalar_one().user_id
    return body["id"], user_id


async def _add_content_item(creator_id: str, item_id: str, *, status: str = "PUBLISHED", format: str = "short") -> None:
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id=item_id, creator_id=creator_id, topic="t", format=format, status=status))
        await session.commit()


async def test_ingest_then_list_performance(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}
    await _add_content_item(creator_id, "cnt_proute1")

    resp = await client.post(
        f"/creators/{creator_id}/content/cnt_proute1/performance", json={"views": 1200, "likes": 80}, headers=headers
    )
    assert resp.status_code == 201
    assert resp.json()["views"] == 1200

    list_resp = await client.get(f"/creators/{creator_id}/content/cnt_proute1/performance", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_ingest_unknown_content_item_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="perf-route2@example.com", name="Perf2")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(
        f"/creators/{creator_id}/content/cnt_missing/performance", json={"views": 100}, headers=headers
    )
    assert resp.status_code == 404


async def test_diagnose_without_metrics_is_409(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="perf-route3@example.com", name="Perf3")
    headers = {"X-Debug-User-Id": user_id}
    await _add_content_item(creator_id, "cnt_proute3")

    resp = await client.post(f"/creators/{creator_id}/content/cnt_proute3/performance/diagnose", headers=headers)
    assert resp.status_code == 409


async def test_diagnose_in_stub_mode_skips_rather_than_guesses(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="perf-route4@example.com", name="Perf4")
    headers = {"X-Debug-User-Id": user_id}
    await _add_content_item(creator_id, "cnt_proute4")
    await client.post(f"/creators/{creator_id}/content/cnt_proute4/performance", json={"views": 100}, headers=headers)

    resp = await client.post(f"/creators/{creator_id}/content/cnt_proute4/performance/diagnose", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["diagnosis"] is None
    assert any("baseline" in w.lower() or "sample" in w.lower() for w in body["warnings"])


async def test_overview_only_lists_published_items_with_latest_snapshot(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="perf-route5@example.com", name="Perf5")
    headers = {"X-Debug-User-Id": user_id}
    await _add_content_item(creator_id, "cnt_proute5_pub", status="PUBLISHED")
    await _add_content_item(creator_id, "cnt_proute5_draft", status="REVIEW")
    await client.post(f"/creators/{creator_id}/content/cnt_proute5_pub/performance", json={"views": 500}, headers=headers)

    resp = await client.get(f"/creators/{creator_id}/performance/overview", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["content_item_id"] == "cnt_proute5_pub"
    assert body[0]["latest_snapshot"]["views"] == 500


async def test_performance_routes_require_ownership(client):
    creator_id, _user_id = await _create_creator_and_get_user_id(client, email="perf-route6@example.com", name="Perf6")
    await _add_content_item(creator_id, "cnt_proute6")
    other_headers = {"X-Debug-User-Id": "usr_someone_else"}

    resp = await client.get(f"/creators/{creator_id}/content/cnt_proute6/performance", headers=other_headers)
    assert resp.status_code == 404
