from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class TimestampMixin:
    """Every table gets created_at/updated_at (CLAUDE.md 14)."""

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class CreatorScopedMixin:
    """Every creator-scoped table carries creator_id (CLAUDE.md 3.1, 14).

    Tenant isolation is enforced at the query layer (see app/api/deps.py:
    get_current_creator_id) — every creator-scoped read/write must filter on
    this column. Never expose one creator's rows to another creator's requests.
    """

    @declared_attr
    def creator_id(cls) -> Mapped[str]:  # noqa: N805
        return mapped_column(String, ForeignKey("creators.id", ondelete="CASCADE"), index=True)
