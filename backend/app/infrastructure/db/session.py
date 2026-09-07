from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from app.core.config import get_settings

settings = get_settings()

# NOTE: if pointing DATABASE_URL at Supabase's transaction pooler (port 6543),
# asyncpg's prepared-statement caching breaks. Use the session pooler / direct
# connection (port 5432) instead, or pass connect_args={"statement_cache_size": 0}.
#
# NullPool: connections aren't reused across checkouts. This trades a little
# connection-setup latency for safety against asyncpg connections being reused
# across event loops (a real hazard with per-test event loops in the test
# suite, and Supabase's own pooler already handles pooling in front of us).
engine = create_async_engine(settings.database_url, echo=False, poolclass=NullPool)

AsyncSessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session
