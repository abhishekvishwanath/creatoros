from sqlalchemy import select

from app.domain.creator.models import Creator, CreatorProfile, VoiceProfile
from app.infrastructure.db.session import AsyncSessionLocal


async def _create_creator_and_get_user_id(client, **overrides):
    payload = {"email": "alice@example.com", "name": "Alice", "niche": "AI productivity"}
    payload.update(overrides)
    resp = await client.post("/creators", json=payload)
    assert resp.status_code == 201
    body = resp.json()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Creator).where(Creator.id == body["id"]))
        user_id = result.scalar_one().user_id
    return body["id"], user_id


async def test_analyze_creates_a_versioned_creator_profile(client):
    """No ANTHROPIC_API_KEY is configured in the test environment, so this
    exercises the full pipeline (context builder -> orchestrator -> agent ->
    state service -> DB) end to end against the model router's stub path —
    exactly the path CLAUDE.md's agent contracts are meant to keep safe."""
    creator_id, user_id = await _create_creator_and_get_user_id(client)
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(f"/creators/{creator_id}/analyze", headers=headers)
    assert resp.status_code == 200
    state = resp.json()["state"]

    assert state["positioning"] is not None
    assert state["positioning"]["positioning_statement"]
    assert state["positioning"]["confidence"] == 0.3

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CreatorProfile).where(CreatorProfile.creator_id == creator_id)
        )
        profiles = result.scalars().all()
    assert len(profiles) == 1
    assert profiles[0].version == 1
    assert profiles[0].is_current is True


async def test_analyze_twice_versions_instead_of_overwriting(client):
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="bob@example.com", name="Bob")
    headers = {"X-Debug-User-Id": user_id}

    await client.post(f"/creators/{creator_id}/analyze", headers=headers)
    await client.post(f"/creators/{creator_id}/analyze", headers=headers)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CreatorProfile).where(CreatorProfile.creator_id == creator_id)
        )
        profiles = result.scalars().all()

    assert len(profiles) == 2
    current = [p for p in profiles if p.is_current]
    assert len(current) == 1
    assert current[0].version == 2


async def test_analyze_carries_forward_boundaries_it_did_not_touch(client):
    """CreatorIntelligenceAgent only proposes positioning/expertise/bio — a
    re-analyze must not wipe out boundaries a creator set some other way
    (regression test for the profile-versioning field-reset bug)."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="dana@example.com", name="Dana")
    headers = {"X-Debug-User-Id": user_id}

    await client.post(f"/creators/{creator_id}/analyze", headers=headers)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CreatorProfile).where(
                CreatorProfile.creator_id == creator_id, CreatorProfile.is_current.is_(True)
            )
        )
        current = result.scalar_one()
        current.prohibited_topics = ["gambling"]
        await session.commit()

    await client.post(f"/creators/{creator_id}/analyze", headers=headers)

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(CreatorProfile).where(
                CreatorProfile.creator_id == creator_id, CreatorProfile.is_current.is_(True)
            )
        )
        new_current = result.scalar_one()

    assert new_current.version == 2
    assert new_current.prohibited_topics == ["gambling"]


async def test_analyze_without_content_never_proposes_a_voice_profile(client):
    """No ANTHROPIC_API_KEY is configured, and voice inference has no honest
    rule-based fallback (unlike positioning) — it should be skipped entirely,
    not filled in with a guess, when there's no ingested content either."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="henry@example.com", name="Henry")
    headers = {"X-Debug-User-Id": user_id}

    resp = await client.post(f"/creators/{creator_id}/analyze", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["state"]["voice"] is None

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(VoiceProfile).where(VoiceProfile.creator_id == creator_id))
        assert result.scalars().first() is None


async def test_analyze_with_ingested_content_still_skips_voice_in_stub_mode(client):
    """Even with content ingested, stub mode (no ANTHROPIC_API_KEY) has no
    honest way to infer voice, so it must still skip rather than guess —
    this is the regression the agent's stub branch exists to prevent."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="ivy@example.com", name="Ivy")
    headers = {"X-Debug-User-Id": user_id}

    await client.post(
        f"/creators/{creator_id}/content",
        json={"title": "A post", "transcript": "hook body cta"},
        headers=headers,
    )

    resp = await client.post(f"/creators/{creator_id}/analyze", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["state"]["voice"] is None


async def test_analyze_skips_pillars_below_minimum_content(client):
    """Stub mode never proposes pillars anyway (no honest fallback), but this
    also covers the below-threshold path: with only 2 pieces of content
    (PILLAR_ANALYSIS_MIN_ITEMS is 3), pillar analysis shouldn't even run."""
    creator_id, user_id = await _create_creator_and_get_user_id(client, email="jack@example.com", name="Jack")
    headers = {"X-Debug-User-Id": user_id}

    for i in range(2):
        await client.post(
            f"/creators/{creator_id}/content",
            json={"title": f"Post {i}", "transcript": "some content"},
            headers=headers,
        )

    resp = await client.post(f"/creators/{creator_id}/analyze", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["state"]["content_pillars"] == []


async def test_analyze_enforces_tenant_isolation(client):
    creator_id, _ = await _create_creator_and_get_user_id(client)
    resp = await client.post(
        f"/creators/{creator_id}/analyze", headers={"X-Debug-User-Id": "usr_someone_else"}
    )
    assert resp.status_code == 404
