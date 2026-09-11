from sqlalchemy import select

from app.domain.creator.models import Creator
from app.domain.research.models import Opportunity
from app.infrastructure.db.session import AsyncSessionLocal


async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "flynn@example.com", "name": "Flynn", "niche": "personal finance"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == body["id"]))
        user_id = result.scalar_one().user_id
    return body["id"], user_id


async def _add_opportunity(creator_id: str, opp_id: str = "opp_seed") -> None:
    async with AsyncSessionLocal() as session:
        session.add(Opportunity(id=opp_id, creator_id=creator_id, topic="budgeting", format="short", status="approved"))
        await session.commit()


async def test_create_from_opportunity_and_fetch_detail(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}
    await _add_opportunity(creator_id)

    resp = await client.post(
        f"/creators/{creator_id}/content/from-opportunity", json={"opportunity_id": "opp_seed"}, headers=headers
    )
    assert resp.status_code == 201
    item = resp.json()
    assert item["topic"] == "budgeting"
    assert item["status"] == "APPROVED"

    detail_resp = await client.get(f"/creators/{creator_id}/content/{item['id']}", headers=headers)
    assert detail_resp.status_code == 200
    body = detail_resp.json()
    assert body["item"]["id"] == item["id"]
    assert body["brief"] is None
    assert body["scripts"] == []


async def test_create_from_unknown_opportunity_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="gwen@example.com", name="Gwen")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(
        f"/creators/{creator_id}/content/from-opportunity", json={"opportunity_id": "opp_missing"}, headers=headers
    )
    assert resp.status_code == 404


async def test_generate_brief_in_stub_mode_skips_rather_than_guesses(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="hank@example.com", name="Hank")
    headers = {"X-Debug-User-Id": user_id}
    await _add_opportunity(creator_id)
    item_resp = await client.post(
        f"/creators/{creator_id}/content/from-opportunity", json={"opportunity_id": "opp_seed"}, headers=headers
    )
    content_item_id = item_resp.json()["id"]

    resp = await client.post(f"/creators/{creator_id}/content/{content_item_id}/generate-brief", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert body["brief"] is None
    assert any("skipped" in w.lower() or "not configured" in w.lower() for w in body["warnings"])


async def test_generate_script_without_brief_is_409(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="iris@example.com", name="Iris")
    headers = {"X-Debug-User-Id": user_id}
    await _add_opportunity(creator_id)
    item_resp = await client.post(
        f"/creators/{creator_id}/content/from-opportunity", json={"opportunity_id": "opp_seed"}, headers=headers
    )
    content_item_id = item_resp.json()["id"]

    resp = await client.post(f"/creators/{creator_id}/content/{content_item_id}/generate-script", headers=headers)
    assert resp.status_code == 409


async def test_review_unknown_script_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="jai@example.com", name="Jai")
    headers = {"X-Debug-User-Id": user_id}
    await _add_opportunity(creator_id)
    item_resp = await client.post(
        f"/creators/{creator_id}/content/from-opportunity", json={"opportunity_id": "opp_seed"}, headers=headers
    )
    content_item_id = item_resp.json()["id"]

    resp = await client.post(
        f"/creators/{creator_id}/content/{content_item_id}/review",
        json={"script_id": "scr_missing"},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_content_pipeline_enforces_tenant_isolation(client):
    creator_id, _ = await _create_creator_and_get_user_id(client, email="kira@example.com", name="Kira")
    resp = await client.get(f"/creators/{creator_id}/content/cnt_missing", headers={"X-Debug-User-Id": "usr_someone_else"})
    assert resp.status_code == 404


async def test_repurpose_without_source_text_is_409(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="lena@example.com", name="Lena")
    headers = {"X-Debug-User-Id": user_id}
    ingest_resp = await client.post(
        f"/creators/{creator_id}/content",
        json={"title": "No transcript video", "platform": "youtube", "format": "long", "topic": "budgeting"},
        headers=headers,
    )
    content_item_id = ingest_resp.json()["id"]

    resp = await client.post(
        f"/creators/{creator_id}/content/{content_item_id}/repurpose",
        json={"target_platform": "x", "target_format": "thread"},
        headers=headers,
    )
    assert resp.status_code == 409


async def test_repurpose_in_stub_mode_skips_rather_than_guesses(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="milo@example.com", name="Milo")
    headers = {"X-Debug-User-Id": user_id}
    ingest_resp = await client.post(
        f"/creators/{creator_id}/content",
        json={
            "title": "Budgeting deep dive",
            "platform": "youtube",
            "format": "long",
            "topic": "budgeting",
            "transcript": "Full transcript about the envelope budgeting method with three examples.",
        },
        headers=headers,
    )
    content_item_id = ingest_resp.json()["id"]

    resp = await client.post(
        f"/creators/{creator_id}/content/{content_item_id}/repurpose",
        json={"target_platform": "x", "target_format": "thread"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["derivative"] is None
    assert any("skipped" in w.lower() or "not configured" in w.lower() for w in body["warnings"])

    derivatives_resp = await client.get(f"/creators/{creator_id}/content/{content_item_id}/derivatives", headers=headers)
    assert derivatives_resp.status_code == 200
    assert derivatives_resp.json() == []


async def test_repurpose_unknown_content_item_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="nia@example.com", name="Nia")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(
        f"/creators/{creator_id}/content/cnt_missing/repurpose",
        json={"target_platform": "x", "target_format": "thread"},
        headers=headers,
    )
    assert resp.status_code == 404
