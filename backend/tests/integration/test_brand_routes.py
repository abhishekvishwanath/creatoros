async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "brand-route@example.com", "name": "Brand", "niche": "productivity"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    return body["id"], body["user_id"]


async def test_create_then_list_brands(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="brand-route1@example.com", name="B1")
    headers = {"X-Debug-User-Id": user_id}

    create_resp = await client.post(
        f"/creators/{creator_id}/brands",
        json={"name": "Notion", "category": "productivity software"},
        headers=headers,
    )
    assert create_resp.status_code == 201
    body = create_resp.json()
    assert body["name"] == "Notion"
    assert body["source"] == "creator_provided"
    assert body["status"] == "candidate"

    list_resp = await client.get(f"/creators/{creator_id}/brands", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_get_unknown_brand_is_404(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="brand-route2@example.com", name="B2")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.get(f"/creators/{creator_id}/brands/brand_missing", headers=headers)
    assert resp.status_code == 404


async def test_brands_are_scoped_to_owning_creator(client):
    creator_a, user_a = await _create_creator_and_get_user_id(client, email="brand-route3@example.com", name="A")
    creator_b, user_b = await _create_creator_and_get_user_id(client, email="brand-route4@example.com", name="B")
    create_resp = await client.post(
        f"/creators/{creator_a}/brands", json={"name": "Notion"}, headers={"X-Debug-User-Id": user_a}
    )
    brand_id = create_resp.json()["id"]

    resp = await client.get(f"/creators/{creator_a}/brands/{brand_id}", headers={"X-Debug-User-Id": user_b})
    assert resp.status_code == 404


async def test_add_and_list_contacts(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="brand-route5@example.com", name="B5")
    headers = {"X-Debug-User-Id": user_id}
    brand_id = (
        await client.post(f"/creators/{creator_id}/brands", json={"name": "Notion"}, headers=headers)
    ).json()["id"]

    add_resp = await client.post(
        f"/creators/{creator_id}/brands/{brand_id}/contacts",
        json={"name": "Jane Doe", "role": "Creator Partnerships", "email": "jane@notion.so"},
        headers=headers,
    )
    assert add_resp.status_code == 201
    assert add_resp.json()["verification_state"] == "unverified"

    list_resp = await client.get(f"/creators/{creator_id}/brands/{brand_id}/contacts", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_add_contact_to_another_creators_brand_is_404(client):
    creator_a, user_a = await _create_creator_and_get_user_id(client, email="brand-route6@example.com", name="A6")
    creator_b, user_b = await _create_creator_and_get_user_id(client, email="brand-route7@example.com", name="B7")
    brand_id = (
        await client.post(f"/creators/{creator_a}/brands", json={"name": "Notion"}, headers={"X-Debug-User-Id": user_a})
    ).json()["id"]

    resp = await client.post(
        f"/creators/{creator_a}/brands/{brand_id}/contacts",
        json={"name": "Someone"},
        headers={"X-Debug-User-Id": user_b},
    )
    assert resp.status_code == 404


async def test_add_and_list_signals(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="brand-route8@example.com", name="B8")
    headers = {"X-Debug-User-Id": user_id}
    brand_id = (
        await client.post(f"/creators/{creator_id}/brands", json={"name": "Notion"}, headers=headers)
    ).json()["id"]

    add_resp = await client.post(
        f"/creators/{creator_id}/brands/{brand_id}/signals",
        json={"summary": "Launched a creator ambassador program", "signal_type": "creator_program"},
        headers=headers,
    )
    assert add_resp.status_code == 201
    assert add_resp.json()["evidence_quality"] == "medium"

    list_resp = await client.get(f"/creators/{creator_id}/brands/{brand_id}/signals", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1


async def test_signals_for_another_creators_brand_is_404(client):
    creator_a, user_a = await _create_creator_and_get_user_id(client, email="brand-route9@example.com", name="A9")
    creator_b, user_b = await _create_creator_and_get_user_id(client, email="brand-route10@example.com", name="B10")
    brand_id = (
        await client.post(f"/creators/{creator_a}/brands", json={"name": "Notion"}, headers={"X-Debug-User-Id": user_a})
    ).json()["id"]

    resp = await client.get(
        f"/creators/{creator_a}/brands/{brand_id}/signals", headers={"X-Debug-User-Id": user_b}
    )
    assert resp.status_code == 404
