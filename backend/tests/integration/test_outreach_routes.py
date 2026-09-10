async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "outreach-route@example.com", "name": "Outreach", "niche": "cooking"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    return body["id"], body["user_id"]


async def _score_a_brand(client, creator_id, headers, brand_name="Notion"):
    brand_id = (
        await client.post(f"/creators/{creator_id}/brands", json={"name": brand_name}, headers=headers)
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
        return brand_id, opportunity.id


async def _score_and_brief_a_brand(client, creator_id, headers, brand_name="Notion"):
    brand_id, opportunity_id = await _score_a_brand(client, creator_id, headers, brand_name)

    from app.domain.commercial.service import apply_campaign_brief
    from app.infrastructure.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        await apply_campaign_brief(
            session,
            brand_opportunity_id=opportunity_id,
            data={"campaign_concept": "A workflow walkthrough", "pitch_angle": "Show, don't tell"},
            evidence_signal_ids=[],
            confidence=0.4,
        )
        await session.commit()
    return brand_id, opportunity_id


async def _create_thread_and_draft_message(creator_id, opportunity_id, kind="initial_pitch", status="draft"):
    from app.domain.commercial.service import add_outreach_message, create_outreach_thread
    from app.infrastructure.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        thread = await create_outreach_thread(session, creator_id=creator_id, brand_opportunity_id=opportunity_id)
        await session.commit()
        thread_id = thread.id

    async with AsyncSessionLocal() as session:
        message = await add_outreach_message(
            session, thread_id=thread_id, direction="outbound", kind=kind, subject="s", body="b", status=status
        )
        await session.commit()
        message_id = message.id
    return thread_id, message_id


async def test_create_outreach_thread_in_stub_mode_returns_no_thread(client):
    """No ANTHROPIC/GROQ key in the test environment — drafting has no
    honest rule-based fallback, so nothing is persisted, mirroring
    scoring/campaign-brief's stub-mode behavior."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route1@example.com", name="O1")
    headers = {"X-Debug-User-Id": user_id}
    _, opportunity_id = await _score_and_brief_a_brand(client, creator_id, headers)

    resp = await client.post(f"/creators/{creator_id}/brand-opportunities/{opportunity_id}/outreach", json={}, headers=headers)
    assert resp.status_code == 201
    body = resp.json()
    assert body["thread"] is None
    assert body["message"] is None
    assert len(body["warnings"]) > 0

    # And nothing was left behind in the pipeline.
    pipeline = await client.get(f"/creators/{creator_id}/outreach", headers=headers)
    assert pipeline.json() == []


async def test_create_outreach_thread_requires_a_campaign_brief_first(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route2@example.com", name="O2")
    headers = {"X-Debug-User-Id": user_id}
    _, opportunity_id = await _score_a_brand(client, creator_id, headers)

    resp = await client.post(f"/creators/{creator_id}/brand-opportunities/{opportunity_id}/outreach", json={}, headers=headers)
    assert resp.status_code == 400


async def test_create_outreach_thread_unknown_opportunity_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route3@example.com", name="O3")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(f"/creators/{creator_id}/brand-opportunities/bopp_missing/outreach", json={}, headers=headers)
    assert resp.status_code == 404


async def test_create_outreach_thread_unknown_contact_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route4@example.com", name="O4")
    headers = {"X-Debug-User-Id": user_id}
    _, opportunity_id = await _score_and_brief_a_brand(client, creator_id, headers)

    resp = await client.post(
        f"/creators/{creator_id}/brand-opportunities/{opportunity_id}/outreach",
        json={"contact_id": "bcontact_missing"},
        headers=headers,
    )
    assert resp.status_code == 404


async def test_list_and_get_outreach_thread(client):
    """End-to-end via the service layer directly (stub mode means the
    create route never produces a real thread) — proves the read routes
    surface whatever exists, regardless of how it got there."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route5@example.com", name="O5")
    headers = {"X-Debug-User-Id": user_id}
    brand_id, opportunity_id = await _score_and_brief_a_brand(client, creator_id, headers, brand_name="Notion")
    thread_id, message_id = await _create_thread_and_draft_message(creator_id, opportunity_id)

    resp = await client.get(f"/creators/{creator_id}/outreach", headers=headers)
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["thread"]["id"] == thread_id
    assert body[0]["brand"]["name"] == "Notion"

    resp = await client.get(f"/creators/{creator_id}/outreach/{thread_id}", headers=headers)
    assert resp.status_code == 200
    detail = resp.json()
    assert detail["thread"]["status"] == "drafting"
    assert detail["brand"]["name"] == "Notion"
    assert len(detail["messages"]) == 1
    assert detail["messages"][0]["id"] == message_id


async def test_get_unknown_thread_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route6@example.com", name="O6")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.get(f"/creators/{creator_id}/outreach/othread_missing", headers=headers)
    assert resp.status_code == 404


async def test_approve_then_mark_sent_happy_path(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route7@example.com", name="O7")
    headers = {"X-Debug-User-Id": user_id}
    _, opportunity_id = await _score_and_brief_a_brand(client, creator_id, headers)
    thread_id, message_id = await _create_thread_and_draft_message(creator_id, opportunity_id)

    resp = await client.patch(f"/creators/{creator_id}/outreach/{thread_id}/messages/{message_id}/approve", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"

    resp = await client.patch(f"/creators/{creator_id}/outreach/{thread_id}/messages/{message_id}/mark-sent", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "sent"
    assert resp.json()["sent_at"] is not None


async def test_mark_sent_before_approve_is_409(client):
    """The human-in-the-loop gate (CLAUDE.md §70) enforced end-to-end
    through the route, not just the service function."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route8@example.com", name="O8")
    headers = {"X-Debug-User-Id": user_id}
    _, opportunity_id = await _score_and_brief_a_brand(client, creator_id, headers)
    thread_id, message_id = await _create_thread_and_draft_message(creator_id, opportunity_id)

    resp = await client.patch(f"/creators/{creator_id}/outreach/{thread_id}/messages/{message_id}/mark-sent", headers=headers)
    assert resp.status_code == 409


async def test_approve_twice_is_409(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route9@example.com", name="O9")
    headers = {"X-Debug-User-Id": user_id}
    _, opportunity_id = await _score_and_brief_a_brand(client, creator_id, headers)
    thread_id, message_id = await _create_thread_and_draft_message(creator_id, opportunity_id)

    resp = await client.patch(f"/creators/{creator_id}/outreach/{thread_id}/messages/{message_id}/approve", headers=headers)
    assert resp.status_code == 200
    resp = await client.patch(f"/creators/{creator_id}/outreach/{thread_id}/messages/{message_id}/approve", headers=headers)
    assert resp.status_code == 409


async def test_draft_follow_up_in_stub_mode_returns_no_message(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route10@example.com", name="O10")
    headers = {"X-Debug-User-Id": user_id}
    _, opportunity_id = await _score_and_brief_a_brand(client, creator_id, headers)
    thread_id, message_id = await _create_thread_and_draft_message(creator_id, opportunity_id)
    await client.patch(f"/creators/{creator_id}/outreach/{thread_id}/messages/{message_id}/approve", headers=headers)
    await client.patch(f"/creators/{creator_id}/outreach/{thread_id}/messages/{message_id}/mark-sent", headers=headers)

    resp = await client.post(f"/creators/{creator_id}/outreach/{thread_id}/follow-up", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["message"] is None
    assert len(resp.json()["warnings"]) > 0


async def test_draft_follow_up_before_initial_pitch_sent_is_400(client):
    """A follow-up only makes sense once the initial pitch has actually
    gone out — a thread still 'drafting' (initial pitch not yet approved
    or sent) must reject a follow-up draft rather than let the creator
    draft correspondence for a conversation that hasn't started."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route13@example.com", name="O13")
    headers = {"X-Debug-User-Id": user_id}
    _, opportunity_id = await _score_and_brief_a_brand(client, creator_id, headers)
    thread_id, _ = await _create_thread_and_draft_message(creator_id, opportunity_id)

    resp = await client.post(f"/creators/{creator_id}/outreach/{thread_id}/follow-up", headers=headers)
    assert resp.status_code == 400


async def test_outreach_routes_are_scoped_to_owning_creator(client):
    creator_a, user_a = await _create_creator_and_get_user_id(client, email="outreach-route11@example.com", name="A11")
    creator_b, user_b = await _create_creator_and_get_user_id(client, email="outreach-route12@example.com", name="B12")
    headers_a = {"X-Debug-User-Id": user_a}
    headers_b = {"X-Debug-User-Id": user_b}
    _, opportunity_id = await _score_and_brief_a_brand(client, creator_a, headers_a)
    thread_id, message_id = await _create_thread_and_draft_message(creator_a, opportunity_id)

    resp = await client.get(f"/creators/{creator_b}/outreach", headers=headers_b)
    assert resp.status_code == 200
    assert resp.json() == []

    resp = await client.get(f"/creators/{creator_b}/outreach/{thread_id}", headers=headers_b)
    assert resp.status_code == 404

    resp = await client.patch(f"/creators/{creator_b}/outreach/{thread_id}/messages/{message_id}/approve", headers=headers_b)
    assert resp.status_code == 404

    resp = await client.post(f"/creators/{creator_b}/brand-opportunities/{opportunity_id}/outreach", json={}, headers=headers_b)
    assert resp.status_code == 404
