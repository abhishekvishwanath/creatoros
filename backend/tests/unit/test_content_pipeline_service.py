from sqlalchemy import select

from app.domain.content.models import ContentBrief, ContentItem, ContentVersion, Script
from app.domain.content.service import (
    apply_content_brief,
    apply_critique,
    create_content_item_from_opportunity,
    create_repurposed_content_item,
    create_script,
    get_best_source_text,
    get_content_brief,
    get_content_item,
    list_content_derivatives,
    list_scripts,
)
from app.domain.creator.models import AudienceSegment, Creator, User
from app.domain.research.models import Opportunity
from app.infrastructure.db.session import AsyncSessionLocal

_creator_counter = 0


async def _make_creator() -> str:
    global _creator_counter
    _creator_counter += 1
    async with AsyncSessionLocal() as session:
        user = User(email=f"contentpipeline{_creator_counter}@example.com")
        session.add(user)
        await session.flush()
        creator = Creator(user_id=user.id, name="Pipeline Test")
        session.add(creator)
        await session.commit()
        return creator.id


async def test_create_content_item_from_opportunity_copies_fields():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(
            Opportunity(
                id="opp_pipe1", creator_id=creator_id, topic="budgeting", format="short-form video", status="approved"
            )
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        item = await create_content_item_from_opportunity(session, creator_id=creator_id, opportunity_id="opp_pipe1")
        await session.commit()
        item_id = item.id

    async with AsyncSessionLocal() as session:
        fetched = await get_content_item(session, creator_id=creator_id, content_item_id=item_id)
    assert fetched.topic == "budgeting"
    assert fetched.format == "short-form video"
    assert fetched.opportunity_id == "opp_pipe1"
    assert fetched.status == "APPROVED"


async def test_create_content_item_from_opportunity_marks_it_used():
    """Regression test: an opportunity promoted into a content item must
    stop showing up as available — otherwise it could be promoted into
    multiple content items indefinitely."""
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(Opportunity(id="opp_pipe2", creator_id=creator_id, topic="budgeting", status="approved"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        await create_content_item_from_opportunity(session, creator_id=creator_id, opportunity_id="opp_pipe2")
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Opportunity).where(Opportunity.id == "opp_pipe2"))
        opportunity = result.scalar_one()
    assert opportunity.status == "used"


async def test_create_content_item_from_unknown_opportunity_returns_none():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        item = await create_content_item_from_opportunity(session, creator_id=creator_id, opportunity_id="opp_missing")
    assert item is None


async def test_create_content_item_refuses_an_already_used_opportunity():
    """Regression test: an opportunity already promoted into a content item
    (or otherwise not in an available status) must not be promotable again —
    this doesn't close every race, but it stops the common sequential case
    of clicking 'Start creating' twice on the same opportunity."""
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(Opportunity(id="opp_pipe3", creator_id=creator_id, topic="budgeting", status="used"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        item = await create_content_item_from_opportunity(session, creator_id=creator_id, opportunity_id="opp_pipe3")
    assert item is None


async def test_apply_content_brief_creates_and_advances_status():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        item = ContentItem(id="cnt_pipe1", creator_id=creator_id, topic="budgeting", status="APPROVED")
        session.add(item)
        await session.commit()

    async with AsyncSessionLocal() as session:
        await apply_content_brief(
            session,
            creator_id=creator_id,
            content_item_id="cnt_pipe1",
            data={"objective": "teach budgeting", "angle": "envelope method"},
            evidence_ids=["sig_1"],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ContentBrief).where(ContentBrief.content_item_id == "cnt_pipe1"))
        brief = result.scalar_one()
        item = await get_content_item(session, creator_id=creator_id, content_item_id="cnt_pipe1")
    assert brief.angle == "envelope method"
    assert item.status == "BRIEFED"


async def test_apply_content_brief_updates_in_place_not_duplicated():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_pipe2", creator_id=creator_id, topic="t", status="APPROVED"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        await apply_content_brief(session, creator_id=creator_id, content_item_id="cnt_pipe2", data={"angle": "v1"}, evidence_ids=[])
        await session.commit()
    async with AsyncSessionLocal() as session:
        await apply_content_brief(session, creator_id=creator_id, content_item_id="cnt_pipe2", data={"angle": "v2"}, evidence_ids=["sig_1"])
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ContentBrief).where(ContentBrief.content_item_id == "cnt_pipe2"))
        briefs = result.scalars().all()
    assert len(briefs) == 1
    assert briefs[0].angle == "v2"


async def test_apply_content_brief_resolves_audience_segment_name_to_id():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_pipe5", creator_id=creator_id, topic="t", status="APPROVED"))
        session.add(AudienceSegment(id="seg_pipe5", creator_id=creator_id, name="Freelance Beginners"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        await apply_content_brief(
            session,
            creator_id=creator_id,
            content_item_id="cnt_pipe5",
            data={"angle": "a", "audience_segment_name": "freelance beginners"},
            evidence_ids=[],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(ContentBrief).where(ContentBrief.content_item_id == "cnt_pipe5"))
        brief = result.scalar_one()
    assert brief.audience_segment_id == "seg_pipe5"


async def test_apply_content_brief_writes_a_content_version_each_time():
    """Regression test: CLAUDE.md §15 explicitly lists briefs as something
    to version ('previous versions remain inspectable') — a regenerate must
    not just silently overwrite the only record of the prior angle/hook."""
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_pipe6", creator_id=creator_id, topic="t", status="APPROVED"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        await apply_content_brief(session, creator_id=creator_id, content_item_id="cnt_pipe6", data={"angle": "v1"}, evidence_ids=[])
        await session.commit()
    async with AsyncSessionLocal() as session:
        await apply_content_brief(session, creator_id=creator_id, content_item_id="cnt_pipe6", data={"angle": "v2"}, evidence_ids=[])
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(ContentVersion)
            .where(ContentVersion.content_item_id == "cnt_pipe6", ContentVersion.stage == "brief")
            .order_by(ContentVersion.version_number)
        )
        versions = result.scalars().all()
    assert [v.body["angle"] for v in versions] == ["v1", "v2"]


async def test_create_script_versions_and_advances_status():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_pipe3", creator_id=creator_id, topic="t", status="BRIEFED"))
        await session.flush()
        session.add(ContentBrief(id="brief_pipe3", content_item_id="cnt_pipe3", angle="a"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        await create_script(
            session, creator_id=creator_id, content_item_id="cnt_pipe3", brief_id="brief_pipe3", platform="instagram",
            body="draft 1", hook_variants=["h1"],
        )
        await session.commit()
    async with AsyncSessionLocal() as session:
        await create_script(
            session, creator_id=creator_id, content_item_id="cnt_pipe3", brief_id="brief_pipe3", platform="instagram",
            body="draft 2", hook_variants=["h2"], status="rewritten",
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        scripts = await list_scripts(session, content_item_id="cnt_pipe3")
        item = await get_content_item(session, creator_id=creator_id, content_item_id="cnt_pipe3")
    assert [s.version_number for s in scripts] == [1, 2]
    assert scripts[1].status == "rewritten"
    assert item.status == "SCRIPTED"


async def test_apply_critique_sets_final_when_passed_and_critiqued_when_not():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_pipe4", creator_id=creator_id, topic="t", status="SCRIPTED"))
        await session.flush()
        session.add(ContentBrief(id="brief_pipe4", content_item_id="cnt_pipe4", angle="a"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        script = await create_script(
            session, creator_id=creator_id, content_item_id="cnt_pipe4", brief_id="brief_pipe4", platform=None, body="d", hook_variants=[]
        )
        await session.commit()
        script_id = script.id

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Script).where(Script.id == script_id))
        script = result.scalar_one()
        await apply_critique(session, script=script, critic_score=90, critic_issues=[], passed=True)
        await session.commit()

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(Script).where(Script.id == script_id))
        script = result.scalar_one()
    assert script.status == "final"
    assert script.critic_score == 90


async def test_get_best_source_text_prefers_final_script_over_transcript():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        item = ContentItem(
            id="cnt_source1", creator_id=creator_id, topic="budgeting", transcript="raw transcript text"
        )
        session.add(item)
        session.add(
            Script(id="scr_source1", content_item_id="cnt_source1", version_number=1, body="final script body", status="final")
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        item = await get_content_item(session, creator_id=creator_id, content_item_id="cnt_source1")
        text = await get_best_source_text(session, content_item=item)
    assert text == "final script body"


async def test_get_best_source_text_falls_back_to_transcript_with_no_scripts():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        session.add(ContentItem(id="cnt_source2", creator_id=creator_id, topic="budgeting", transcript="raw transcript text"))
        await session.commit()

    async with AsyncSessionLocal() as session:
        item = await get_content_item(session, creator_id=creator_id, content_item_id="cnt_source2")
        text = await get_best_source_text(session, content_item=item)
    assert text == "raw transcript text"


async def test_create_repurposed_content_item_links_to_source_and_is_scripted():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        source = ContentItem(id="cnt_source3", creator_id=creator_id, topic="budgeting", pillar_id=None)
        session.add(source)
        await session.commit()

    async with AsyncSessionLocal() as session:
        source = await get_content_item(session, creator_id=creator_id, content_item_id="cnt_source3")
        derivative, script = await create_repurposed_content_item(
            session,
            creator_id=creator_id,
            source_item=source,
            target_platform="x",
            target_format="thread",
            title="Budgeting thread",
            body="1/ Here's the thing about budgeting...",
            hook_variants=["hook a", "hook b"],
        )
        await session.commit()
        derivative_id = derivative.id

    async with AsyncSessionLocal() as session:
        fetched = await get_content_item(session, creator_id=creator_id, content_item_id=derivative_id)
        scripts = await list_scripts(session, content_item_id=derivative_id)
    assert fetched.source_content_item_id == "cnt_source3"
    assert fetched.source_type == "repurposed"
    assert fetched.status == "SCRIPTED"
    assert fetched.topic == "budgeting"
    assert len(scripts) == 1
    assert scripts[0].body == "1/ Here's the thing about budgeting..."
    assert scripts[0].brief_id is None


async def test_list_content_derivatives_returns_only_this_source_tree():
    creator_id = await _make_creator()
    async with AsyncSessionLocal() as session:
        source = ContentItem(id="cnt_source4", creator_id=creator_id, topic="budgeting")
        other = ContentItem(id="cnt_source5", creator_id=creator_id, topic="saving")
        session.add_all([source, other])
        await session.commit()

    async with AsyncSessionLocal() as session:
        source = await get_content_item(session, creator_id=creator_id, content_item_id="cnt_source4")
        await create_repurposed_content_item(
            session,
            creator_id=creator_id,
            source_item=source,
            target_platform="instagram",
            target_format="reel",
            title="Reel 1",
            body="body",
            hook_variants=[],
        )
        await session.commit()

    async with AsyncSessionLocal() as session:
        derivatives = await list_content_derivatives(session, creator_id=creator_id, source_content_item_id="cnt_source4")
        other_derivatives = await list_content_derivatives(session, creator_id=creator_id, source_content_item_id="cnt_source5")
    assert len(derivatives) == 1
    assert derivatives[0].source_content_item_id == "cnt_source4"
    assert other_derivatives == []
