"""Content pipeline: pillars, items, versions, briefs, scripts, calendar
(CLAUDE.md 14, 22, 23, 26)."""

from datetime import datetime
from typing import Optional

from pgvector.sqlalchemy import Vector
from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String, Text
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

    source_type: Mapped[str] = mapped_column(String, default="created")  # ingested | created
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    topic: Mapped[Optional[str]] = mapped_column(String, nullable=True)


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
    __tablename__ = "scripts"

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
    __tablename__ = "calendar_events"

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
