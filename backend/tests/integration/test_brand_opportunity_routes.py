async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "bopp-route@example.com", "name": "BOpp", "niche": "cooking"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    return body["id"], body["user_id"]


async def test_score_in_stub_mode_returns_no_opportunity(client):
    """No ANTHROPIC/GROQ key in the test environment (conftest forces stub
    mode) — scoring has no honest rule-based fallback, so it must skip
    rather than guess (mirrors every other synthesis agent's stub-mode
    behavior)."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="bopp-route1@example.com", name="B1")
    headers = {"X-Debug-User-Id": user_id}
    brand_id = (
        await client.post(f"/creators/{creator_id}/brands", json={"name": "Notion"}, headers=headers)
    ).json()["id"]

    resp = await client.post(f"/creators/{creator_id}/brands/{brand_id}/opportunities/score", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["opportunity"] is None
    assert len(resp.json()["warnings"]) > 0


async def test_score_unknown_brand_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="bopp-route2@example.com", name="B2")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(f"/creators/{creator_id}/brands/brand_missing/opportunities/score", headers=headers)
    assert resp.status_code == 404


async def test_radar_lists_scored_brands_ranked(client):
    """End-to-end via the service layer directly (stub mode means the route
    itself never produces a real score) — proves the radar endpoint reads
    whatever scores exist, regardless of how they got there."""
    from app.domain.commercial.service import apply_brand_opportunity_score, create_brand
    from app.infrastructure.db.session import AsyncSessionLocal

    creator_id, user_id = await _create_creator_and_get_user_id(client, email="bopp-route3@example.com", name="B3")
    headers = {"X-Debug-User-Id": user_id}

    async with AsyncSessionLocal() as session:
        brand = await create_brand(session, creator_id=creator_id, data={"name": "Notion", "category": "productivity"})
        await session.commit()
        brand_id = brand.id

    async with AsyncSessionLocal() as session:
        await apply_brand_opportunity_score(
            session,
            creator_id=creator_id,
            brand_id=brand_id,
            score_components={
                "audience_fit": 0.8,
                "creator_fit": 0.7,
                "product_content_fit": 0.7,
                "timing_signal": 0.5,
                "historical_category_fit": 0.5,
            },
            contactability=0.5,
            reasons="Good overlap",
            evidence_signal_ids=[],
            suggested_contact_roles=["Creator Partnerships Manager"],
            confidence=0.55,
        )
        await session.commit()

    resp = await client.get(f"/creators/{creator_id}/brand-opportunities", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["brand"]["name"] == "Notion"
    assert body[0]["opportunity"]["reasons"] == "Good overlap"


async def test_radar_is_scoped_to_owning_creator(client):
    from app.domain.commercial.service import apply_brand_opportunity_score, create_brand
    from app.infrastructure.db.session import AsyncSessionLocal

    creator_a, user_a = await _create_creator_and_get_user_id(client, email="bopp-route4@example.com", name="A4")
    creator_b, user_b = await _create_creator_and_get_user_id(client, email="bopp-route5@example.com", name="B5")

    async with AsyncSessionLocal() as session:
        brand = await create_brand(session, creator_id=creator_a, data={"name": "Notion"})
        await session.commit()
        await apply_brand_opportunity_score(
            session,
            creator_id=creator_a,
            brand_id=brand.id,
            score_components={"audience_fit": 0.5, "creator_fit": 0.5, "product_content_fit": 0.5, "timing_signal": 0.5, "historical_category_fit": 0.5},
            contactability=0.0,
            reasons="",
            evidence_signal_ids=[],
            suggested_contact_roles=[],
            confidence=0.3,
        )
        await session.commit()

    resp = await client.get(f"/creators/{creator_b}/brand-opportunities", headers={"X-Debug-User-Id": user_b})
    assert resp.status_code == 200
    assert resp.json() == []
