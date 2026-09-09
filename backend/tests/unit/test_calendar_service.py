from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.core.ids import generate_id
from app.domain.content.models import CalendarEvent, ContentItem, PublishedContent
from app.domain.content.service import (
    get_content_bottlenecks,
    list_calendar_events,
    mark_content_stage,
    publish_content_item,
    schedule_content_item,
)
from app.domain.creator.models import Creator, User
from app.domain.creator.service import get_weekly_capacity, set_weekly_capacity
from app.infrastructure.db.session import AsyncSessionLocal

_creator_counter = 0


async def _make_creator() -> str:
    global _creator_counter
    _creator_counter += 1
    async with AsyncSessionLocal() as session:
        user = User(email=f"calendar{_creator_counter}@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Calendar Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def test_mark_content_stage_advances_from_review_to_recorded():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_cal1", creator_id=creator_id, topic="t", status="REVIEW"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        item = await mark_content_stage(session, content_item_id="cnt_cal1", to_status="RECORDED")
        await session.commit()
    assert item.status == "RECORDED"


async def test_mark_content_stage_rejects_invalid_transition():
    """Regression guard: RECORDED can only follow REVIEW, not be set from an
    arbitrary earlier stage — otherwise a creator could skip straight past
    brief/script/critique by hitting the wrong button."""
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_cal2", creator_id=creator_id, topic="t", status="APPROVED"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        with pytest.raises(ValueError):
            await mark_content_stage(session, content_item_id="cnt_cal2", to_status="RECORDED")


async def test_mark_content_stage_rejects_unknown_status():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_cal3", creator_id=creator_id, topic="t", status="REVIEW"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        with pytest.raises(ValueError):
            await mark_content_stage(session, content_item_id="cnt_cal3", to_status="PUBLISHED")


async def test_schedule_content_item_creates_calendar_event_and_advances_status():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_cal4", creator_id=creator_id, topic="t", status="REVIEW", platform="instagram"))
        await session.commit()

    scheduled_at = datetime.now(timezone.utc) + timedelta(days=1)
    async with AsyncSessionLocal() as session:
        item, event = await schedule_content_item(
            session, content_item_id="cnt_cal4", scheduled_at=scheduled_at, platform=None
        )
        await session.commit()

    assert item.status == "SCHEDULED"
    assert event.status == "scheduled"
    assert event.platform == "instagram"  # falls back to the content item's platform


async def test_schedule_content_item_rejects_wrong_status():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_cal5", creator_id=creator_id, topic="t", status="IDEA"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        with pytest.raises(ValueError):
            await schedule_content_item(
                session, content_item_id="cnt_cal5", scheduled_at=datetime.now(timezone.utc), platform="tiktok"
            )


async def test_rescheduling_updates_existing_event_not_duplicates():
    """Regression test: calling schedule twice on the same content item
    (e.g. the creator picks a new date) must update the one CalendarEvent
    row, not silently accumulate duplicates that would double-count in
    get_content_bottlenecks / list_calendar_events."""
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_cal6", creator_id=creator_id, topic="t", status="REVIEW"))
        await session.commit()

    first_time = datetime.now(timezone.utc) + timedelta(days=1)
    second_time = datetime.now(timezone.utc) + timedelta(days=3)
    async with AsyncSessionLocal() as session:
        await schedule_content_item(session, content_item_id="cnt_cal6", scheduled_at=first_time, platform="x")
        await session.commit()
    async with AsyncSessionLocal() as session:
        # status is SCHEDULED, still within SCHEDULABLE_FROM territory is false —
        # re-scheduling an already-scheduled item is allowed by picking a new date
        # only if still in an allowed source status; simulate the common case of
        # re-scheduling before it moves past SCHEDULED by resetting to REVIEW.
        item = await session.get(ContentItem, "cnt_cal6")
        item.status = "REVIEW"
        await session.commit()
    async with AsyncSessionLocal() as session:
        await schedule_content_item(session, content_item_id="cnt_cal6", scheduled_at=second_time, platform="x")
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CalendarEvent).where(CalendarEvent.content_item_id == "cnt_cal6"))
        events = result.scalars().all()
    assert len(events) == 1
    assert events[0].scheduled_at.replace(tzinfo=timezone.utc) - second_time < timedelta(seconds=1)


async def test_db_rejects_a_second_calendar_event_for_the_same_content_item():
    """Regression test for the uq_calendar_events_content_item constraint:
    schedule_content_item's SELECT-then-insert-or-update is not race-safe on
    its own (two concurrent calls could both see no existing row) — this
    proves the DB-level constraint is the actual backstop, independent of
    that service function's happy-path logic."""
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_cal_dupe", creator_id=creator_id, topic="t", status="REVIEW"))
        await session.flush()
        session.add(
            CalendarEvent(
                id=generate_id("calendar_event"),
                creator_id=creator_id,
                content_item_id="cnt_cal_dupe",
                status="planned",
            )
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        session.add(
            CalendarEvent(
                id=generate_id("calendar_event"),
                creator_id=creator_id,
                content_item_id="cnt_cal_dupe",
                status="planned",
            )
        )
        with pytest.raises(IntegrityError):
            await session.commit()


async def test_publish_content_item_creates_published_row_and_advances_status():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_cal7", creator_id=creator_id, topic="t", status="REVIEW", platform="youtube"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        await schedule_content_item(
            session, content_item_id="cnt_cal7", scheduled_at=datetime.now(timezone.utc), platform="youtube"
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        item, published = await publish_content_item(
            session, content_item_id="cnt_cal7", url="https://example.com/v", external_id="ext_1"
        )
        await session.commit()

    assert item.status == "PUBLISHED"
    assert published.platform == "youtube"

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(CalendarEvent).where(CalendarEvent.content_item_id == "cnt_cal7"))
        event = result.scalar_one()
    assert event.status == "published"


async def test_publish_content_item_rejects_wrong_status():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_cal8", creator_id=creator_id, topic="t", status="REVIEW"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        with pytest.raises(ValueError):
            await publish_content_item(session, content_item_id="cnt_cal8", url=None, external_id=None)


async def test_publish_content_item_requires_a_resolvable_platform():
    """Regression test: PublishedContent.platform is a non-nullable column —
    without this guard, publishing a content item that was scheduled with no
    platform on either the item or the event would hit an IntegrityError
    instead of a clear 409."""
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_cal9", creator_id=creator_id, topic="t", status="REVIEW"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        await schedule_content_item(
            session, content_item_id="cnt_cal9", scheduled_at=datetime.now(timezone.utc), platform=None
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        with pytest.raises(ValueError):
            await publish_content_item(session, content_item_id="cnt_cal9", url=None, external_id=None)


async def test_list_calendar_events_filters_by_date_range():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_cal10", creator_id=creator_id, topic="t", status="REVIEW"))
        session.add(ContentItem(id="cnt_cal11", creator_id=creator_id, topic="t2", status="REVIEW"))
        await session.commit()

    near = datetime.now(timezone.utc) + timedelta(days=1)
    far = datetime.now(timezone.utc) + timedelta(days=30)
    async with AsyncSessionLocal() as session:
        await schedule_content_item(session, content_item_id="cnt_cal10", scheduled_at=near, platform="x")
        await session.commit()
    async with AsyncSessionLocal() as session:
        await schedule_content_item(session, content_item_id="cnt_cal11", scheduled_at=far, platform="x")
        await session.commit()

    async with AsyncSessionLocal() as session:
        rows = await list_calendar_events(
            session, creator_id=creator_id, start=datetime.now(timezone.utc), end=near + timedelta(days=1)
        )
    assert [item.id for _, item in rows] == ["cnt_cal10"]


async def test_weekly_capacity_get_defaults_to_none_and_set_persists():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        assert await get_weekly_capacity(session, creator_id=creator_id) is None

    async with AsyncSessionLocal() as session:
        await set_weekly_capacity(session, creator_id=creator_id, items_per_week=4)
        await session.commit()

    async with AsyncSessionLocal() as session:
        assert await get_weekly_capacity(session, creator_id=creator_id) == 4


async def test_weekly_capacity_set_twice_updates_in_place():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await set_weekly_capacity(session, creator_id=creator_id, items_per_week=3)
        await session.commit()
    async with AsyncSessionLocal() as session:
        await set_weekly_capacity(session, creator_id=creator_id, items_per_week=7)
        await session.commit()

    async with AsyncSessionLocal() as session:
        assert await get_weekly_capacity(session, creator_id=creator_id) == 7


async def test_bottlenecks_flags_pipeline_backlog():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        for i in range(4):
            session.add(ContentItem(id=f"cnt_bn_approved_{i}", creator_id=creator_id, topic="t", status="APPROVED"))
        session.add(ContentItem(id="cnt_bn_scripted", creator_id=creator_id, topic="t", status="SCRIPTED"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        bottlenecks = await get_content_bottlenecks(session, creator_id=creator_id)
    types = [b["type"] for b in bottlenecks]
    assert "pipeline_backlog" in types


async def test_bottlenecks_does_not_flag_backlog_when_production_keeps_pace():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_bn_ok_1", creator_id=creator_id, topic="t", status="APPROVED"))
        session.add(ContentItem(id="cnt_bn_ok_2", creator_id=creator_id, topic="t", status="SCRIPTED"))
        session.add(ContentItem(id="cnt_bn_ok_3", creator_id=creator_id, topic="t", status="REVIEW"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        bottlenecks = await get_content_bottlenecks(session, creator_id=creator_id)
    types = [b["type"] for b in bottlenecks]
    assert "pipeline_backlog" not in types


async def test_bottlenecks_flags_over_capacity():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        await set_weekly_capacity(session, creator_id=creator_id, items_per_week=1)
        session.add(ContentItem(id="cnt_bn_cap1", creator_id=creator_id, topic="t", status="REVIEW"))
        session.add(ContentItem(id="cnt_bn_cap2", creator_id=creator_id, topic="t", status="REVIEW"))
        await session.commit()

    soon = datetime.now(timezone.utc) + timedelta(days=2)
    async with AsyncSessionLocal() as session:
        await schedule_content_item(session, content_item_id="cnt_bn_cap1", scheduled_at=soon, platform="x")
        await session.commit()
    async with AsyncSessionLocal() as session:
        await schedule_content_item(session, content_item_id="cnt_bn_cap2", scheduled_at=soon, platform="x")
        await session.commit()

    async with AsyncSessionLocal() as session:
        bottlenecks = await get_content_bottlenecks(session, creator_id=creator_id)
    over_capacity = next(b for b in bottlenecks if b["type"] == "over_capacity")
    assert over_capacity["evidence"]["scheduled"] == 2
    assert over_capacity["evidence"]["weekly_capacity"] == 1


async def test_bottlenecks_flags_missed_schedule():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_bn_missed", creator_id=creator_id, topic="t", status="SCHEDULED"))
        await session.flush()
        session.add(
            CalendarEvent(
                id="cal_bn_missed",
                creator_id=creator_id,
                content_item_id="cnt_bn_missed",
                scheduled_at=datetime.now(timezone.utc) - timedelta(days=2),
                status="scheduled",
            )
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        bottlenecks = await get_content_bottlenecks(session, creator_id=creator_id)
    missed = next(b for b in bottlenecks if b["type"] == "missed_schedule")
    assert missed["evidence"]["missed"] == 1
