async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "cbrief-route@example.com", "name": "CBrief", "niche": "cooking"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    return body["id"], body["user_id"]


async def _score_a_brand(client, creator_id, headers, email_suffix):
    brand_id = (
        await client.post(f"/creators/{creator_id}/brands", json={"name": "Notion"}, headers=headers)
    ).json()["id"]

    from app.domain.commercial.service import apply_brand_opportunity_score
    from app.infrastructure.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        opportunity = await apply_brand_opportunity_score(
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
            suggested_contact_roles=[],
            confidence=0.55,
        )
        await session.commit()
        return opportunity.id


async def test_generate_campaign_brief_in_stub_mode_returns_no_brief(client):
    """No ANTHROPIC/GROQ key in the test environment (conftest forces stub
    mode) — pitch strategy has no honest rule-based fallback, so it must
    skip rather than guess, mirroring brand scoring's stub-mode behavior."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="cbrief-route1@example.com", name="C1")
    headers = {"X-Debug-User-Id": user_id}
    opportunity_id = await _score_a_brand(client, creator_id, headers, "1")

    resp = await client.post(f"/creators/{creator_id}/brand-opportunities/{opportunity_id}/campaign-brief", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["brief"] is None
    assert len(resp.json()["warnings"]) > 0


async def test_generate_campaign_brief_unknown_opportunity_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="cbrief-route2@example.com", name="C2")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(f"/creators/{creator_id}/brand-opportunities/bopp_missing/campaign-brief", headers=headers)
    assert resp.status_code == 404


async def test_get_campaign_brief_returns_null_when_none_generated(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="cbrief-route3@example.com", name="C3")
    headers = {"X-Debug-User-Id": user_id}
    opportunity_id = await _score_a_brand(client, creator_id, headers, "3")

    resp = await client.get(f"/creators/{creator_id}/brand-opportunities/{opportunity_id}/campaign-brief", headers=headers)
    assert resp.status_code == 200
    assert resp.json() is None


async def test_get_campaign_brief_returns_generated_brief(client):
    """End-to-end via the service layer directly (stub mode means the route
    itself never produces a real brief) — proves the GET endpoint reads
    whatever brief exists, regardless of how it got there."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="cbrief-route4@example.com", name="C4")
    headers = {"X-Debug-User-Id": user_id}
    opportunity_id = await _score_a_brand(client, creator_id, headers, "4")

    from app.domain.commercial.service import apply_campaign_brief
    from app.infrastructure.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await apply_campaign_brief(
            session,
            brand_opportunity_id=opportunity_id,
            data={"campaign_concept": "A workflow walkthrough"},
            evidence_signal_ids=[],
            confidence=0.4,
        )
        await session.commit()

    resp = await client.get(f"/creators/{creator_id}/brand-opportunities/{opportunity_id}/campaign-brief", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["campaign_concept"] == "A workflow walkthrough"


async def test_campaign_brief_routes_are_scoped_to_owning_creator(client):
    creator_a, user_a = await _create_creator_and_get_user_id(client, email="cbrief-route5@example.com", name="A5")
    creator_b, user_b = await _create_creator_and_get_user_id(client, email="cbrief-route6@example.com", name="B6")
    headers_a = {"X-Debug-User-Id": user_a}
    headers_b = {"X-Debug-User-Id": user_b}
    opportunity_id = await _score_a_brand(client, creator_a, headers_a, "5")

    resp = await client.get(f"/creators/{creator_b}/brand-opportunities/{opportunity_id}/campaign-brief", headers=headers_b)
    assert resp.status_code == 404

    resp = await client.post(f"/creators/{creator_b}/brand-opportunities/{opportunity_id}/campaign-brief", headers=headers_b)
    assert resp.status_code == 404
