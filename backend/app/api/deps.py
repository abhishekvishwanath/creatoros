from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.creator.models import Creator
from app.infrastructure.db.session import get_db

DbSession = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user_id(
    x_debug_user_id: Optional[str] = Header(default=None, alias="X-Debug-User-Id"),
) -> str:
    """Resolves the authenticated user's id.

    TODO(auth): replace with verification of the Supabase-issued JWT from the
    `Authorization` header once Supabase Auth is wired into the frontend
    (CLAUDE.md 46: enforce authorization on every creator-scoped operation).
    Until then, the caller identifies itself via `X-Debug-User-Id` so every
    downstream tenant-isolation check below is real and exercised end-to-end
    ahead of swapping in real auth — nothing here changes when auth lands.
    """
    if not x_debug_user_id:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Missing X-Debug-User-Id header (real auth not wired yet — see app/api/deps.py)",
        )
    return x_debug_user_id


async def get_owned_creator(
    creator_id: str,
    db: DbSession,
    user_id: str = Depends(get_current_user_id),
) -> Creator:
    """Tenant isolation gate (CLAUDE.md 3.1, 46): every creator-scoped route
    depends on this instead of loading by creator_id alone, so one user can
    never read or mutate another user's creator data."""
    result = await db.execute(select(Creator).where(Creator.id == creator_id))
    creator = result.scalar_one_or_none()
    if creator is None or creator.user_id != user_id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Creator not found")
    return creator
