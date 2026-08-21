"""Integration test fixtures.

These tests run against a real Postgres (via `docker compose up postgres` locally,
or the `postgres` service container in `.github/workflows/ci.yml`) — not SQLite.
The schema uses Postgres-specific types (JSONB, native ENUM, UUID) precisely
because that's what production runs on; a SQLite stand-in would validate a
different database than the one this system ships on, which defeats the point.
"""

from __future__ import annotations

import os

import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from trialready_api.db.models import Base

DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql+asyncpg://trialready:trialready@localhost:5432/trialready"
)


@pytest_asyncio.fixture
async def engine():
    # Function-scoped, not session-scoped: asyncpg connections are bound to the
    # event loop they were created on, and pytest-asyncio gives each test
    # function its own event loop by default. A session-scoped engine reused
    # across tests would hand test 2 a connection created on test 1's
    # (now-closed) loop — the exact shape of the "another operation is in
    # progress" error this used to throw. `create_all` is checkfirst=True by
    # default, so re-running it per test against the same database is a cheap
    # no-op after the first test creates the schema.
    eng = create_async_engine(DATABASE_URL, future=True)
    async with eng.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db_session(engine) -> AsyncSession:
    """One outer transaction + SAVEPOINT per test, rolled back afterward, so
    tests never see each other's data and service-layer `session.commit()`
    calls don't leak past the test boundary. This is SQLAlchemy 2.0's documented
    `join_transaction_mode="create_savepoint"` pattern for exactly this case —
    see "Joining a Session into an External Transaction" in the SQLAlchemy docs.
    """
    async with engine.connect() as conn:
        await conn.begin()
        session_factory = async_sessionmaker(
            bind=conn,
            expire_on_commit=False,
            class_=AsyncSession,
            join_transaction_mode="create_savepoint",
        )
        async with session_factory() as session:
            yield session
        await conn.rollback()
