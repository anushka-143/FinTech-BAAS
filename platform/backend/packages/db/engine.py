"""Async SQLAlchemy 2 engine and session factory.

Two connection pools:
  1. Primary (read-write) — for transactional business logic
  2. Read-only — for AI queries, analytics, reports

In development, both point to the same DB.
In production, readonly points to a Postgres streaming replica.
"""

from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from packages.core.settings import get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_readonly_engine: AsyncEngine | None = None
_readonly_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_size=settings.database_pool_size,
            max_overflow=settings.database_max_overflow,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=settings.environment == "development",
        )
    return _engine


def get_readonly_engine() -> AsyncEngine:
    """Engine for read-only queries (AI, analytics, reports).

    Falls back to primary engine if no readonly URL is configured.
    """
    global _readonly_engine
    if _readonly_engine is None:
        settings = get_settings()
        readonly_url = settings.database_readonly_url
        if not readonly_url:
            return get_engine()  # Fallback to primary in dev
        _readonly_engine = create_async_engine(
            readonly_url,
            pool_size=10,
            max_overflow=5,
            pool_pre_ping=True,
            pool_recycle=3600,
            echo=False,
        )
    return _readonly_engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _session_factory


def get_readonly_session_factory() -> async_sessionmaker[AsyncSession]:
    global _readonly_session_factory
    if _readonly_session_factory is None:
        _readonly_session_factory = async_sessionmaker(
            bind=get_readonly_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _readonly_session_factory


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a transactional async session."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_readonly_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for read-only queries (AI, analytics).

    Does NOT commit — all queries are read-only.
    AI agents, copilots, and investigation tools should use this
    to avoid competing with transactional writes on the primary DB.
    """
    factory = get_readonly_session_factory()
    async with factory() as session:
        yield session


async def dispose_engine() -> None:
    global _engine, _session_factory, _readonly_engine, _readonly_session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
    if _readonly_engine is not None:
        await _readonly_engine.dispose()
        _readonly_engine = None
        _readonly_session_factory = None
