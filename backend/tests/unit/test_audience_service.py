from sqlalchemy import select

from app.domain.creator.models import AudienceProfile, AudienceSegment, Creator, User
from app.domain.creator.service import (
    apply_audience_profile_update,
    apply_audience_segments,
    ingest_audience_signal,
    list_audience_signals,
)
from app.infrastructure.db.session import AsyncSessionLocal

_creator_counter = 0


async def _make_creator() -> str:
    global _creator_counter
    _creator_counter += 1
    async with AsyncSessionLocal() as session:
        user = User(email=f"audiencetest{_creator_counter}@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Audience Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def test_ingest_and_list_audience_signals():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await ingest_audience_signal(
            session, creator_id=creator_id, data={"text": "How do I start budgeting?", "source_platform": "instagram"}
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        signals = await list_audience_signals(session, creator_id=creator_id)
    assert len(signals) == 1
    assert signals[0].text == "How do I start budgeting?"


async def test_apply_audience_profile_update_versions_instead_of_overwriting():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await apply_audience_profile_update(
            session,
            creator_id=creator_id,
            data={"knowledge_level": "beginner"},
            confidence=0.4,
            evidence_ids=["asig_1"],
        )
        await session.commit()
    async with AsyncSessionLocal() as session:
        await apply_audience_profile_update(
            session,
            creator_id=creator_id,
            data={"knowledge_level": "intermediate"},
            confidence=0.5,
            evidence_ids=["asig_1", "asig_2"],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AudienceProfile).where(AudienceProfile.creator_id == creator_id)
        )
        profiles = result.scalars().all()
    assert len(profiles) == 2
    current = [p for p in profiles if p.is_current]
    assert len(current) == 1
    assert current[0].version == 2
    assert current[0].knowledge_level == "intermediate"


async def test_apply_audience_profile_update_does_not_null_out_a_field_the_model_explicitly_nulled():
    """Regression test: the profile prompt always emits all six keys, using
    null for 'can't infer this' rather than omitting the key entirely —
    treating 'key present with value null' the same as 'field proposed'
    would silently wipe a previously-known field on every re-analyze whose
    evidence doesn't happen to support it this time."""
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await apply_audience_profile_update(
            session,
            creator_id=creator_id,
            data={"geography": ["US"], "knowledge_level": "beginner"},
            confidence=0.4,
            evidence_ids=["asig_1"],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        await apply_audience_profile_update(
            session,
            creator_id=creator_id,
            data={"geography": None, "knowledge_level": "intermediate"},
            confidence=0.5,
            evidence_ids=["asig_1", "asig_2"],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AudienceProfile).where(AudienceProfile.creator_id == creator_id, AudienceProfile.is_current.is_(True))
        )
        current = result.scalar_one()
    assert current.geography == ["US"]
    assert current.knowledge_level == "intermediate"


async def test_apply_audience_profile_update_sets_sample_size_from_evidence_ids():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await apply_audience_profile_update(
            session,
            creator_id=creator_id,
            data={"knowledge_level": "beginner"},
            confidence=0.4,
            evidence_ids=["asig_1", "asig_2", "asig_3"],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(AudienceProfile).where(AudienceProfile.creator_id == creator_id)
        )
        profile = result.scalar_one()
    assert profile.sample_size == 3


async def test_apply_audience_segments_creates_new_segment():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await apply_audience_segments(
            session,
            creator_id=creator_id,
            segments=[
                {
                    "name": "Budgeting beginners",
                    "problems": ["no system"],
                    "confidence": 0.5,
                    "evidence_ids": ["asig_1", "asig_2"],
                }
            ],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AudienceSegment).where(AudienceSegment.creator_id == creator_id))
        segments = result.scalars().all()
    assert len(segments) == 1
    assert segments[0].problems == ["no system"]
    assert segments[0].sample_size == 2
    assert segments[0].evidence_ids == ["asig_1", "asig_2"]


async def test_apply_audience_segments_updates_existing_by_case_insensitive_name():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await apply_audience_segments(
            session,
            creator_id=creator_id,
            segments=[{"name": "Budgeting beginners", "problems": ["p1"], "evidence_ids": ["asig_1"]}],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        await apply_audience_segments(
            session,
            creator_id=creator_id,
            segments=[{"name": "budgeting beginners", "problems": ["p2"], "evidence_ids": ["asig_1", "asig_2"]}],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AudienceSegment).where(AudienceSegment.creator_id == creator_id))
        segments = result.scalars().all()
    assert len(segments) == 1
    assert segments[0].problems == ["p2"]


async def test_apply_audience_segments_sets_sample_size_to_zero_not_stale_value():
    """Regression test: `len(evidence_ids) or existing.sample_size` treated a
    real, honest zero-evidence update the same as 'not provided' and kept
    the stale sample_size — a re-analyze that genuinely cites zero signals
    for a segment must show 0, not silently keep the old count."""
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await apply_audience_segments(
            session,
            creator_id=creator_id,
            segments=[{"name": "Segment A", "evidence_ids": ["asig_1", "asig_2"]}],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        await apply_audience_segments(
            session, creator_id=creator_id, segments=[{"name": "Segment A", "evidence_ids": []}]
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AudienceSegment).where(AudienceSegment.creator_id == creator_id))
        segment = result.scalar_one()
    assert segment.sample_size == 0


async def test_apply_audience_segments_never_deletes_a_segment_missing_from_new_proposal():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await apply_audience_segments(
            session, creator_id=creator_id, segments=[{"name": "Segment A", "evidence_ids": []}]
        )
        await session.commit()
    async with AsyncSessionLocal() as session:
        await apply_audience_segments(
            session, creator_id=creator_id, segments=[{"name": "Segment B", "evidence_ids": []}]
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(AudienceSegment).where(AudienceSegment.creator_id == creator_id))
        names = {s.name for s in result.scalars().all()}
    assert names == {"Segment A", "Segment B"}
