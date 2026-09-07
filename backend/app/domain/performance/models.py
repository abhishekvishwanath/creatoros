"""Performance ingestion + baselines (CLAUDE.md 27, 28, 29)."""

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import generate_id
from app.infrastructure.db.base import Base, CreatorScopedMixin, TimestampMixin


class PerformanceMetric(Base, TimestampMixin):
    """Raw metric points as ingested from a platform (CLAUDE.md 27)."""

    __tablename__ = "performance_metrics"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("performance_metric"))
    content_item_id: Mapped[str] = mapped_column(
        String, ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    platform: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    metric_name: Mapped[str] = mapped_column(String)
    metric_value: Mapped[float] = mapped_column(Float)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)


class PerformanceSnapshot(Base, TimestampMixin, CreatorScopedMixin):
    """Denormalized per-content snapshot compared against creator baseline
    (CLAUDE.md 28: median of last N posts, not just absolute numbers)."""

    __tablename__ = "performance_snapshots"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("performance_snapshot"))
    content_item_id: Mapped[str] = mapped_column(
        String, ForeignKey("content_items.id", ondelete="CASCADE"), index=True
    )
    views: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    watch_time: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_view_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    retention: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    likes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    comments: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    shares: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    saves: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    followers_gained: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    profile_visits: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    # e.g. {"median_views_30d": 4200, "views_vs_baseline_ratio": 2.1}
    baseline_comparison: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=datetime.utcnow)
