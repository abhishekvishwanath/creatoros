from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app.domain.content.models import ContentItem
from app.domain.creator.models import Creator
from app.infrastructure.db.session import AsyncSessionLocal


async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "cal-route@example.com", "name": "Cal", "niche": "fitness"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == body["id"]))
        user_id = result.scalar_one().user_id
    return body["id"], user_id


async def _add_content_item(creator_id: str, item_id: str, status: str = "REVIEW", platform: str | None = None) -> None:
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id=item_id, creator_id=creator_id, topic="t", status=status, platform=platform))
        await session.commit()


async def test_schedule_then_publish_full_flow(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}
    await _add_content_item(creator_id, "cnt_route1", status="REVIEW", platform="tiktok")

    scheduled_at = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    schedule_resp = await client.post(
        f"/creators/{creator_id}/content/cnt_route1/schedule",
        json={"scheduled_at": scheduled_at},
        headers=headers,
    )
    assert schedule_resp.status_code == 200
    body = schedule_resp.json()
    assert body["item"]["status"] == "SCHEDULED"
    assert body["event"]["platform"] == "tiktok"

    calendar_resp = await client.get(f"/creators/{creator_id}/calendar", headers=headers)
    assert calendar_resp.status_code == 200
    assert len(calendar_resp.json()) == 1
    assert calendar_resp.json()[0]["content_title"] is None or "content_status" in calendar_resp.json()[0]

    publish_resp = await client.post(
        f"/creators/{creator_id}/content/cnt_route1/publish", json={"url": "https://x.com/1"}, headers=headers
    )
    assert publish_resp.status_code == 200
    assert publish_resp.json()["item"]["status"] == "PUBLISHED"
    assert publish_resp.json()["url"] == "https://x.com/1"


async def test_schedule_from_wrong_status_is_409(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="cal-route2@example.com", name="Cal2")
    headers = {"X-Debug-User-Id": user_id}
    await _add_content_item(creator_id, "cnt_route2", status="IDEA")

    resp = await client.post(
        f"/creators/{creator_id}/content/cnt_route2/schedule",
        json={"scheduled_at": datetime.now(timezone.utc).isoformat()},
        headers=headers,
    )
    assert resp.status_code == 409


async def test_schedule_unknown_content_item_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="cal-route3@example.com", name="Cal3")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(
        f"/creators/{creator_id}/content/cnt_missing/schedule",
        json={"scheduled_at": datetime.now(timezone.utc).isoformat()},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_mark_recorded_then_editing_flow(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="cal-route4@example.com", name="Cal4")
    headers = {"X-Debug-User-Id": user_id}
    await _add_content_item(creator_id, "cnt_route4", status="REVIEW")

    recorded_resp = await client.post(f"/creators/{creator_id}/content/cnt_route4/mark-recorded", headers=headers)
    assert recorded_resp.status_code == 200
    assert recorded_resp.json()["status"] == "RECORDED"

    editing_resp = await client.post(f"/creators/{creator_id}/content/cnt_route4/mark-editing", headers=headers)
    assert editing_resp.status_code == 200
    assert editing_resp.json()["status"] == "EDITING"

    # Can't mark recorded again from EDITING.
    repeat_resp = await client.post(f"/creators/{creator_id}/content/cnt_route4/mark-recorded", headers=headers)
    assert repeat_resp.status_code == 409


async def test_capacity_get_defaults_and_can_be_set(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="cal-route5@example.com", name="Cal5")
    headers = {"X-Debug-User-Id": user_id}

    get_resp = await client.get(f"/creators/{creator_id}/capacity", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["items_per_week"] is None

    put_resp = await client.put(f"/creators/{creator_id}/capacity", json={"items_per_week": 5}, headers=headers)
    assert put_resp.status_code == 200
    assert put_resp.json()["items_per_week"] == 5

    get_again = await client.get(f"/creators/{creator_id}/capacity", headers=headers)
    assert get_again.json()["items_per_week"] == 5


async def test_capacity_rejects_out_of_range_value(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="cal-route6@example.com", name="Cal6")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.put(f"/creators/{creator_id}/capacity", json={"items_per_week": 0}, headers=headers)
    assert resp.status_code == 422


async def test_bottlenecks_endpoint_returns_list(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="cal-route7@example.com", name="Cal7")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.get(f"/creators/{creator_id}/calendar/bottlenecks", headers=headers)
    assert resp.status_code == 200
    assert resp.json() == []


async def test_calendar_routes_require_ownership(client):
    creator_id, _user_id = await _create_creator_and_get_user_id(client, email="cal-route8@example.com", name="Cal8")
    other_headers = {"X-Debug-User-Id": "usr_someone_else"}

    resp = await client.get(f"/creators/{creator_id}/calendar", headers=other_headers)
    assert resp.status_code == 404
