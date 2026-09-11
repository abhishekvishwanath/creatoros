"""Content pipeline: pillars, items, versions, briefs, scripts, calendar
(CLAUDE.md 14, 22, 23, 26)."""

from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import generate_id
from app.infrastructure.db.base import Base, CreatorScopedMixin, TimestampMixin

# CLAUDE.md 26 content state machine
CONTENT_STATES = [
    "IDEA",
    "APPROVED",
    "BRIEFED",
    "SCRIPTED",
    "RECORDED",
    "EDITING",
    "REVIEW",
    "SCHEDULED",
    "PUBLISHED",
    "ANALYZING",
    "LEARNED",
]


class ContentPillar(Base, TimestampMixin, CreatorScopedMixin):
    __tablename__ = "content_pillars"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("content_pillar"))
    name: Mapped[str] = mapped_column(String)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    weight: Mapped[float] = mapped_column(Float, default=1.0)


class ContentItem(Base, TimestampMixin, CreatorScopedMixin):
    __tablename__ = "content_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("content_item"))
    title: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    platform: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    format: Mapped[Optional[str]] = mapped_column(String, nullable=True)  # short | long | carousel | thread | post
    status: Mapped[str] = mapped_column(String, default="IDEA")

    pillar_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("content_pillars.id", ondelete="SET NULL"), nullable=True
    )
    opportunity_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True
    )

    source_type: Mapped[str] = mapped_column(String, default="created")  # ingested | created | repurposed
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topic: Mapped[Optional[str]] = mapped_column(String, nullable=True)

    # Set only when source_type == "repurposed" (CLAUDE.md §25 content tree:
    # "1 YouTube video -> 3 Reels -> 1 Carousel -> ..."). SET NULL rather than
    # CASCADE on the source's deletion: a derivative that's already been
    # scripted/scheduled/published is real, independent content in its own
    # right and shouldn't vanish just because its source asset was later
    # removed (CLAUDE.md §15 spirit — don't erase state on a side effect).
    source_content_item_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("content_items.id", ondelete="SET NULL"), nullable=True, index=True
    )


class ContentVersion(Base, TimestampMixin):
    """Immutable version history for a content item at any pipeline stage
    (CLAUDE.md 15: never overwrite important history)."""

    __tablename__ = "content_versions"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("content_version"))
    content_item_id: Mapped[str] = mapped_column(
        String, ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    version_number: Mapped[int] = mapped_column(Integer)
    stage: Mapped[str] = mapped_column(String)  # brief | script | critique | rewrite | final
    body: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_by: Mapped[str] = mapped_column(String, default="agent")  # agent | human


class ContentAsset(Base, TimestampMixin):
    __tablename__ = "content_assets"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("content_asset"))
    content_item_id: Mapped[str] = mapped_column(
        String, ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    asset_type: Mapped[str] = mapped_column(String)  # video | image | audio | document
    storage_ref: Mapped[Optional[str]] = mapped_column(String, nullable=True)


class ContentEmbedding(Base, TimestampMixin, CreatorScopedMixin):
    """Semantic memory (CLAUDE.md 6.2): pgvector embeddings for scripts,
    statements, audience comments, research snippets, learnings."""

    __tablename__ = "content_embeddings"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("content_embedding"))
    content_item_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("content_items.id", ondelete="CASCADE"), nullable=True
    )
    source_type: Mapped[str] = mapped_column(String)  # script | statement | comment | research | learning
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list] = mapped_column(Vector(1536))


class ContentBrief(Base, TimestampMixin):
    """CLAUDE.md 22 content brief required fields."""

    __tablename__ = "content_briefs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("content_brief"))
    content_item_id: Mapped[str] = mapped_column(
        String, ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    objective: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    audience_segment_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("audience_segments.id", ondelete="SET NULL"), nullable=True
    )
    core_insight: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    angle: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    hook_type: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    hook: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    narrative_structure: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    key_points: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    examples: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    broll_suggestions: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    on_screen_text: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    pacing: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    cta: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    caption_concept: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    cover_concept: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    repurposing_opportunities: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    evidence_ids: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    risk_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Script(Base, TimestampMixin):
    """Versioned by version_number (CLAUDE.md §15). Uniquely constrained per
    content item so a race between two concurrent generate-script/review
    calls fails loudly (an IntegrityError) rather than silently producing
    two scripts sharing a version number, which would break the ordering
    list_scripts and the UI's version picker both assume."""

    __tablename__ = "scripts"
    __table_args__ = (
        UniqueConstraint("content_item_id", "version_number", name="uq_scripts_content_item_version"),
    )

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("script"))
    content_item_id: Mapped[str] = mapped_column(
        String, ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    brief_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("content_briefs.id", ondelete="SET NULL"), nullable=True
    )
    version_number: Mapped[int] = mapped_column(Integer, default=1)
    platform: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    body: Mapped[str] = mapped_column(Text)
    hook_variants: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft")  # draft | critiqued | rewritten | final
    critic_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    critic_issues: Mapped[Optional[list]] = mapped_column(JSON, nullable=True)


class CalendarEvent(Base, TimestampMixin, CreatorScopedMixin):
    """At most one calendar event per content item — enforced at the DB
    level (not just app/domain/content/service.py::schedule_content_item's
    update-in-place logic), the same reasoning as Script's version_number
    constraint: without it, two concurrent schedule calls on the same item
    could each see no existing row and both insert one, silently duplicating
    it in list_calendar_events and double-counting it in
    get_content_bottlenecks. Nullable content_item_id still allows many NULLs
    (Postgres doesn't treat NULL as equal to NULL under a unique constraint)."""

    __tablename__ = "calendar_events"
    __table_args__ = (UniqueConstraint("content_item_id", name="uq_calendar_events_content_item"),)

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("calendar_event"))
    content_item_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("content_items.id", ondelete="CASCADE"), nullable=True
    )
    scheduled_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    platform: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="planned")  # planned | scheduled | published | missed


class PublishedContent(Base, TimestampMixin):
    __tablename__ = "published_content"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("published_content"))
    content_item_id: Mapped[str] = mapped_column(
        String, ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[str] = mapped_column(String)
    external_id: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
