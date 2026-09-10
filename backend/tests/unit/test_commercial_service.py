from app.domain.commercial.service import apply_commercial_profile_update, get_current_commercial_profile
from app.domain.creator.models import Creator, User
from app.infrastructure.db.session import AsyncSessionLocal

_creator_counter = 0


async def _make_creator() -> str:
    global _creator_counter
    _creator_counter += 1
    async with AsyncSessionLocal() as session:
        user = User(email=f"commercial{_creator_counter}@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Commercial Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def test_get_current_returns_none_when_no_profile_exists():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        profile = await get_current_commercial_profile(session, creator_id=creator_id)
    assert profile is None


async def test_apply_update_creates_first_version():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        profile = await apply_commercial_profile_update(
            session,
            creator_id=creator_id,
            data={"ideal_sponsor_categories": ["AI tools", "productivity software"]},
        )
        await session.commit()

    assert profile.version == 1
    assert profile.is_current is True
    assert profile.ideal_sponsor_categories == ["AI tools", "productivity software"]
    assert profile.confidence == 1.0


async def test_apply_update_supersedes_without_losing_unset_fields():
    """Regression guard matching app/domain/creator/service.py's identical
    merge semantics (CLAUDE.md §15): a partial update must never null out a
    field it didn't mention."""
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await apply_commercial_profile_update(
            session,
            creator_id=creator_id,
            data={"ideal_sponsor_categories": ["AI tools"], "prohibited_categories": ["gambling"]},
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        updated = await apply_commercial_profile_update(
            session, creator_id=creator_id, data={"sponsorship_goals": "Land 2 recurring sponsors this quarter"}
        )
        await session.commit()

    assert updated.version == 2
    assert updated.ideal_sponsor_categories == ["AI tools"]
    assert updated.prohibited_categories == ["gambling"]
    assert updated.sponsorship_goals == "Land 2 recurring sponsors this quarter"


async def test_apply_update_supersedes_old_version_is_current_flag():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        first = await apply_commercial_profile_update(session, creator_id=creator_id, data={"revenue_goal": "10k/mo"})
        await session.commit()
        first_id = first.id

    async with AsyncSessionLocal() as session:
        await apply_commercial_profile_update(session, creator_id=creator_id, data={"revenue_goal": "20k/mo"})
        await session.commit()

    async with AsyncSessionLocal() as session:
        from app.domain.commercial.models import CommercialProfile

        old = await session.get(CommercialProfile, first_id)
        current = await get_current_commercial_profile(session, creator_id=creator_id)

    assert old.is_current is False
    assert current.version == 2
    assert current.revenue_goal == "20k/mo"


async def test_commercial_profiles_are_isolated_per_creator():
    creator_a = await _make_creator()
    creator_b = await _make_creator()
    async with AsyncSessionLocal() as session:
        await apply_commercial_profile_update(session, creator_id=creator_a, data={"revenue_goal": "A's goal"})
        await session.commit()

    async with AsyncSessionLocal() as session:
        profile_b = await get_current_commercial_profile(session, creator_id=creator_b)
    assert profile_b is None
