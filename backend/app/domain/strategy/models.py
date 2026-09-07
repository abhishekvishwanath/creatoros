"""Content-as-portfolio strategy (CLAUDE.md 21)."""

from datetime import date
from typing import Optional

from sqlalchemy import Date, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.ids import generate_id
from app.infrastructure.db.base import Base, CreatorScopedMixin, TimestampMixin


class Strategy(Base, TimestampMixin, CreatorScopedMixin):
    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("strategy"))
    period_start: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    period_end: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String, default="draft")  # draft | active | completed


class StrategyItem(Base, TimestampMixin):
    __tablename__ = "strategy_items"

    id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: generate_id("strategy_item"))
    strategy_id: Mapped[str] = mapped_column(String, ForeignKey("strategies.id", ondelete="CASCADE"), index=True)
    opportunity_id: Mapped[Optional[str]] = mapped_column(
        String, ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True
    )
    day_of_week: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # 0=Mon .. 6=Sun
    # reach | authority | community | story | conversion | experimental (CLAUDE.md 21)
    portfolio_role: Mapped[Optional[str]] = mapped_column(String, nullable=True)
    status: Mapped[str] = mapped_column(String, default="planned")
