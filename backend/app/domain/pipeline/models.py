"""Pipeline runs: the "paste a link, everything starts" progress record
(CLAUDE.md §33 Phase 1->4). One row per background run, `stages` holding an
ordered JSON list the frontend polls to animate real backend progress —
not a fake progress bar."""

from typing import Optional

from sqlalchemy import JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import generate_id
from app.infrastructure.db.base import Base, CreatorScopedMixin, TimestampMixin

PIPELINE_STAGE_NAMES = ["import", "creator_dna", "research", "trends", "opportunities", "strategy"]


class PipelineRun(Base, TimestampMixin, CreatorScopedMixin):
    __tablename__ = "pipeline_runs"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("pipeline_run"))
    status: Mapped[str] = mapped_column(String, default="running")  # running | completed | failed
    youtube_url: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    # [{name, status, summary, warnings}, ...] — status per stage:
    # pending | running | success | failed | skipped.
    stages: Mapped[list] = mapped_column(JSON, default=list)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
