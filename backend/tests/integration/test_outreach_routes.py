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


async def _create_sent_thread(client, creator_id, opportunity_id, headers):
    thread_id, message_id = await _create_thread_and_draft_message(creator_id, opportunity_id)
    await client.patch(f"/creators/{creator_id}/outreach/{thread_id}/messages/{message_id}/approve", headers=headers)
    await client.patch(f"/creators/{creator_id}/outreach/{thread_id}/messages/{message_id}/mark-sent", headers=headers)
    return thread_id


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


async def test_record_brand_reply_in_stub_mode_still_saves_the_reply(client):
    """No ANTHROPIC/GROQ key — extraction is skipped, but the reply itself
    (plain data entry, not intelligence) must still be saved (CLAUDE.md
    §43: never lose the creator's own evidence to an agent hiccup)."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route14@example.com", name="O14")
    headers = {"X-Debug-User-Id": user_id}
    _, opportunity_id = await _score_and_brief_a_brand(client, creator_id, headers)
    thread_id = await _create_sent_thread(client, creator_id, opportunity_id, headers)

    resp = await client.post(
        f"/creators/{creator_id}/outreach/{thread_id}/messages",
        json={"body": "We're interested, what's your rate?"},
        headers=headers,
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["message"]["body"] == "We're interested, what's your rate?"
    assert body["message"]["direction"] == "inbound"
    assert body["message"]["extracted_data"] is None
    assert len(body["warnings"]) > 0

    # And the thread advanced to 'replied'.
    detail = await client.get(f"/creators/{creator_id}/outreach/{thread_id}", headers=headers)
    assert detail.json()["thread"]["status"] == "replied"
    assert len(detail.json()["messages"]) == 2


async def test_record_brand_reply_unknown_thread_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route15@example.com", name="O15")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(
        f"/creators/{creator_id}/outreach/othread_missing/messages", json={"body": "hi"}, headers=headers
    )
    assert resp.status_code == 404


async def test_record_brand_reply_before_pitch_sent_is_400(client):
    """A reply only makes sense once the pitch has actually gone out —
    same reasoning as the follow-up route's precondition."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route21@example.com", name="O21")
    headers = {"X-Debug-User-Id": user_id}
    _, opportunity_id = await _score_and_brief_a_brand(client, creator_id, headers)
    thread_id, _ = await _create_thread_and_draft_message(creator_id, opportunity_id)

    resp = await client.post(f"/creators/{creator_id}/outreach/{thread_id}/messages", json={"body": "hi"}, headers=headers)
    assert resp.status_code == 400


async def test_record_decision_accept_updates_thread(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route16@example.com", name="O16")
    headers = {"X-Debug-User-Id": user_id}
    _, opportunity_id = await _score_and_brief_a_brand(client, creator_id, headers)
    thread_id = await _create_sent_thread(client, creator_id, opportunity_id, headers)

    resp = await client.patch(
        f"/creators/{creator_id}/outreach/{thread_id}/decision",
        json={"decision": "accept", "note": "Great fit for the audience"},
        headers=headers,
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "won"
    assert body["outcome"] == "deal_confirmed"
    assert body["creator_decision"] == "accept"
    assert body["creator_decision_note"] == "Great fit for the audience"
    assert body["decided_at"] is not None


async def test_record_decision_rejects_unrecognized_value(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route17@example.com", name="O17")
    headers = {"X-Debug-User-Id": user_id}
    _, opportunity_id = await _score_and_brief_a_brand(client, creator_id, headers)
    thread_id = await _create_sent_thread(client, creator_id, opportunity_id, headers)

    resp = await client.patch(
        f"/creators/{creator_id}/outreach/{thread_id}/decision",
        json={"decision": "sign_the_contract"},
        headers=headers,
    )
    assert resp.status_code == 400


async def test_record_decision_rejects_re_deciding_a_resolved_thread(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route23@example.com", name="O23")
    headers = {"X-Debug-User-Id": user_id}
    _, opportunity_id = await _score_and_brief_a_brand(client, creator_id, headers)
    thread_id = await _create_sent_thread(client, creator_id, opportunity_id, headers)

    resp = await client.patch(
        f"/creators/{creator_id}/outreach/{thread_id}/decision", json={"decision": "accept"}, headers=headers
    )
    assert resp.status_code == 200

    resp = await client.patch(
        f"/creators/{creator_id}/outreach/{thread_id}/decision", json={"decision": "decline"}, headers=headers
    )
    assert resp.status_code == 400


async def test_record_decision_unknown_thread_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route18@example.com", name="O18")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.patch(
        f"/creators/{creator_id}/outreach/othread_missing/decision", json={"decision": "accept"}, headers=headers
    )
    assert resp.status_code == 404


async def test_reply_and_decision_routes_are_scoped_to_owning_creator(client):
    creator_a, user_a = await _create_creator_and_get_user_id(client, email="outreach-route19@example.com", name="A19")
    creator_b, user_b = await _create_creator_and_get_user_id(client, email="outreach-route20@example.com", name="B20")
    headers_a = {"X-Debug-User-Id": user_a}
    headers_b = {"X-Debug-User-Id": user_b}
    _, opportunity_id = await _score_and_brief_a_brand(client, creator_a, headers_a)
    thread_id = await _create_sent_thread(client, creator_a, opportunity_id, headers_a)

    resp = await client.post(f"/creators/{creator_b}/outreach/{thread_id}/messages", json={"body": "hi"}, headers=headers_b)
    assert resp.status_code == 404

    resp = await client.patch(
        f"/creators/{creator_b}/outreach/{thread_id}/decision", json={"decision": "accept"}, headers=headers_b
    )
    assert resp.status_code == 404


async def _create_sent_thread_for_category(client, creator_id, headers, brand_name, category):
    from app.domain.commercial.service import apply_brand_opportunity_score
    from app.infrastructure.db.session import AsyncSessionLocal

    brand_id = (
        await client.post(f"/creators/{creator_id}/brands", json={"name": brand_name, "category": category}, headers=headers)
    ).json()["id"]

    async with AsyncSessionLocal() as session:
        opportunity = await apply_brand_opportunity_score(
            session,
            creator_id=creator_id,
            brand_id=brand_id,
            score_components={"audience_fit": 0.5, "creator_fit": 0.5, "product_content_fit": 0.5, "timing_signal": 0.5, "historical_category_fit": 0.5},
            contactability=0.5,
            reasons="",
            evidence_signal_ids=[],
            suggested_contact_roles=[],
            confidence=0.5,
        )
        await session.commit()
        opportunity_id = opportunity.id

    return await _create_sent_thread(client, creator_id, opportunity_id, headers)


async def test_record_decision_auto_triggers_commercial_learning_sync(client):
    """CLAUDE.md Part II §72: resolving a deal is the trigger point — after
    the second 'accept' for the same brand category, a commercial-category
    StrategicLearning row should exist and be readable via GET /learnings,
    the same table/endpoint the content loop already uses."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="outreach-route22@example.com", name="O22")
    headers = {"X-Debug-User-Id": user_id}

    thread_1 = await _create_sent_thread_for_category(client, creator_id, headers, "Brand A", "AI productivity tools")
    thread_2 = await _create_sent_thread_for_category(client, creator_id, headers, "Brand B", "AI productivity tools")

    resp = await client.patch(f"/creators/{creator_id}/outreach/{thread_1}/decision", json={"decision": "accept"}, headers=headers)
    assert resp.status_code == 200
    # Only one resolved deal so far — not enough evidence yet.
    learnings = (await client.get(f"/creators/{creator_id}/learnings", headers=headers)).json()
    assert not any(l["category"] and l["category"].startswith("commercial/") for l in learnings)

    resp = await client.patch(f"/creators/{creator_id}/outreach/{thread_2}/decision", json={"decision": "accept"}, headers=headers)
    assert resp.status_code == 200

    learnings = (await client.get(f"/creators/{creator_id}/learnings", headers=headers)).json()
    commercial = [l for l in learnings if l["category"] and l["category"].startswith("commercial/positive/")]
    assert len(commercial) == 1
    assert len(commercial[0]["evidence_ids"]) == 2
