async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "commercial-route@example.com", "name": "Commercial", "niche": "finance"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()
    return body["id"], body["user_id"]


async def test_get_commercial_profile_before_any_update_is_null(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="comm-route1@example.com", name="C1")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.get(f"/creators/{creator_id}/commercial-profile", headers=headers)
    assert resp.status_code == 200
    assert resp.json() is None


async def test_put_then_get_commercial_profile(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="comm-route2@example.com", name="C2")
    headers = {"X-Debug-User-Id": user_id}

    put_resp = await client.put(
        f"/creators/{creator_id}/commercial-profile",
        json={
            "ideal_sponsor_categories": ["AI tools", "productivity apps"],
            "prohibited_categories": ["gambling", "alcohol"],
            "sponsorship_goals": "2 recurring sponsors this quarter",
        },
        headers=headers,
    )
    assert put_resp.status_code == 200
    body = put_resp.json()
    assert body["version"] == 1
    assert body["ideal_sponsor_categories"] == ["AI tools", "productivity apps"]
    assert body["confidence"] == 1.0

    get_resp = await client.get(f"/creators/{creator_id}/commercial-profile", headers=headers)
    assert get_resp.status_code == 200
    assert get_resp.json()["sponsorship_goals"] == "2 recurring sponsors this quarter"


async def test_put_twice_versions_without_losing_unset_fields(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="comm-route3@example.com", name="C3")
    headers = {"X-Debug-User-Id": user_id}

    await client.put(
        f"/creators/{creator_id}/commercial-profile",
        json={"ideal_sponsor_categories": ["AI tools"]},
        headers=headers,
    )
    second = await client.put(
        f"/creators/{creator_id}/commercial-profile",
        json={"revenue_goal": "15k/mo"},
        headers=headers,
    )
    assert second.status_code == 200
    body = second.json()
    assert body["version"] == 2
    assert body["ideal_sponsor_categories"] == ["AI tools"]
    assert body["revenue_goal"] == "15k/mo"


async def test_commercial_profile_is_scoped_to_the_owning_creator(client):
    creator_a, user_a = await _create_creator_and_get_user_id(client, email="comm-route4@example.com", name="A")
    creator_b, user_b = await _create_creator_and_get_user_id(client, email="comm-route5@example.com", name="B")
    await client.put(
        f"/creators/{creator_a}/commercial-profile",
        json={"revenue_goal": "A's goal"},
        headers={"X-Debug-User-Id": user_a},
    )

    resp = await client.get(f"/creators/{creator_a}/commercial-profile", headers={"X-Debug-User-Id": user_b})
    assert resp.status_code == 404


async def test_creator_state_snapshot_includes_commercial_profile(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="comm-route6@example.com", name="C6")
    headers = {"X-Debug-User-Id": user_id}
    await client.put(
        f"/creators/{creator_id}/commercial-profile",
        json={"ideal_sponsor_categories": ["AI tools"]},
        headers=headers,
    )

    state_resp = await client.get(f"/creators/{creator_id}/state", headers=headers)
    assert state_resp.status_code == 200
    commercial = state_resp.json()["commercial_profile"]
    assert commercial is not None
    assert commercial["ideal_sponsor_categories"] == ["AI tools"]


async def test_creator_state_snapshot_commercial_profile_is_null_when_unset(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="comm-route7@example.com", name="C7")
    headers = {"X-Debug-User-Id": user_id}

    state_resp = await client.get(f"/creators/{creator_id}/state", headers=headers)
    assert state_resp.status_code == 200
    assert state_resp.json()["commercial_profile"] is None
