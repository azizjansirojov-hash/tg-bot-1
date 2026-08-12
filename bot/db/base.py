"""SQLAlchemy async engine and session factory."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from bot.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine() -> AsyncEngine:
    """
    Lazily create and return the shared async engine.

    Pool settings (from Settings / env):
      - pool_size: base persistent connections
      - max_overflow: burst connections above pool_size
      - pool_timeout: seconds to wait for a free connection
      - pool_recycle: recycle connections after N seconds (stale-conn safety)
      - pool_pre_ping: validate connections before use
    """
    global _engine
    if _engine is None:
        settings = get_settings()
        _engine = create_async_engine(
            settings.database_url,
            pool_pre_ping=True,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            pool_recycle=settings.db_pool_recycle,
        )
    return _engine


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Lazily create and return the shared session factory."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


async def release_session(session: AsyncSession) -> None:
    """
    Commit and close a session early (before long Telegram I/O / flood waits).

    Safe to call multiple times. DbSessionMiddleware skips commit/close when
    the session is already closed.
    """
    if not session.is_active:
        return
    try:
        await session.commit()
    except Exception:
        await session.rollback()
        raise
    finally:
        await session.close()


async def dispose_engine() -> None:
    """Dispose the engine on shutdown."""
    global _engine, _session_factory
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _session_factory = None
