"""Database access helpers. Handlers must not talk to SQLAlchemy directly."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ColumnElement, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.models import AdminAuditLog, Movie, User


async def get_movie_by_code(session: AsyncSession, code: str) -> Movie | None:
    """Return a movie by its unique numeric code, or None."""
    result = await session.execute(select(Movie).where(Movie.code == code))
    return result.scalar_one_or_none()


async def upsert_movie(
    session: AsyncSession,
    *,
    code: str,
    title: str | None,
    file_id: str,
    channel_message_id: int,
    added_by: int,
) -> Movie:
    """Insert or overwrite a movie entry (race-safe ON CONFLICT on code)."""
    now = datetime.now(timezone.utc)
    stmt = (
        insert(Movie)
        .values(
            code=code,
            title=title,
            file_id=file_id,
            channel_message_id=channel_message_id,
            added_by=added_by,
            added_at=now,
        )
        .on_conflict_do_update(
            index_elements=[Movie.code],
            set_={
                "title": title,
                "file_id": file_id,
                "channel_message_id": channel_message_id,
                "added_by": added_by,
                "added_at": now,
            },
        )
        .returning(Movie)
        .execution_options(populate_existing=True)
    )
    result = await session.execute(stmt)
    movie = result.scalar_one()
    await session.flush()
    return movie


async def delete_movie(session: AsyncSession, code: str) -> bool:
    """Delete a movie by code. Returns True if a row was deleted."""
    movie = await get_movie_by_code(session, code)
    if movie is None:
        return False
    await session.delete(movie)
    await session.flush()
    return True


async def list_movies_paginated(
    session: AsyncSession,
    *,
    page: int = 0,
    per_page: int = 10,
) -> tuple[list[Movie], int]:
    """Return a page of movies and total count in one query (window count)."""
    total_col: ColumnElement[int] = func.count().over().label("total_count")
    result = await session.execute(
        select(Movie, total_col)
        .order_by(Movie.code.asc())
        .offset(page * per_page)
        .limit(per_page)
    )
    rows = result.all()
    if not rows:
        # Empty page — still need accurate total (e.g. page past end).
        total = await count_movies(session)
        return [], total
    movies = [row[0] for row in rows]
    total = int(rows[0][1])
    return movies, total


async def count_movies(session: AsyncSession) -> int:
    """Return total number of stored movies."""
    result = await session.execute(select(func.count()).select_from(Movie))
    return int(result.scalar_one())


async def count_users(session: AsyncSession) -> int:
    """Return total number of unique users who requested a code."""
    result = await session.execute(select(func.count()).select_from(User))
    return int(result.scalar_one())


async def upsert_user_activity(session: AsyncSession, telegram_id: int) -> User:
    """Create or update a user on code request (race-safe ON CONFLICT)."""
    now = datetime.now(timezone.utc)
    stmt = (
        insert(User)
        .values(
            telegram_id=telegram_id,
            first_seen=now,
            last_active=now,
            request_count=1,
        )
        .on_conflict_do_update(
            index_elements=[User.telegram_id],
            set_={
                "last_active": now,
                "request_count": User.request_count + 1,
            },
        )
        .returning(User)
        .execution_options(populate_existing=True)
    )
    result = await session.execute(stmt)
    user = result.scalar_one()
    await session.flush()
    return user


async def write_audit_log(
    session: AsyncSession,
    *,
    admin_id: int,
    action: str,
    target: str | None = None,
    details: str | None = None,
) -> AdminAuditLog:
    """Persist an admin mutation audit entry (no file_id / raw text)."""
    entry = AdminAuditLog(
        admin_id=admin_id,
        action=action,
        target=target,
        details=details,
    )
    session.add(entry)
    await session.flush()
    return entry


async def list_audit_logs_paginated(
    session: AsyncSession,
    *,
    page: int = 0,
    per_page: int = 10,
) -> tuple[list[AdminAuditLog], int]:
    """Return a page of audit logs and total in one query (window count)."""
    total_col: ColumnElement[int] = func.count().over().label("total_count")
    result = await session.execute(
        select(AdminAuditLog, total_col)
        .order_by(AdminAuditLog.timestamp.desc(), AdminAuditLog.id.desc())
        .offset(page * per_page)
        .limit(per_page)
    )
    rows = result.all()
    if not rows:
        total_result = await session.execute(
            select(func.count()).select_from(AdminAuditLog)
        )
        return [], int(total_result.scalar_one())
    entries = [row[0] for row in rows]
    total = int(rows[0][1])
    return entries, total
