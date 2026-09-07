import os

os.environ.setdefault(
    "DATABASE_URL", "postgresql+asyncpg://creatoros:creatoros@localhost:5544/creatoros_test"
)

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.infrastructure.db.all_models import Base
from app.infrastructure.db.session import engine


@pytest_asyncio.fixture(autouse=True)
async def _reset_db():
    """Fresh schema per test (CLAUDE.md-scale test suite is small enough that
    simplicity beats per-test transaction rollback performance tricks)."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client():
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
