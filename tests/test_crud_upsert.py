"""CRUD upsert tests — Postgres when TEST_DATABASE_URL is set; else skip integration."""

from __future__ import annotations

import asyncio
import os

import pytest
from bot.db import crud
from bot.db.base import Base
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

pytestmark = pytest.mark.asyncio


def _db_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL")


@pytest.fixture
async def session():
    url = _db_url()
    if not url:
        pytest.skip(
            "TEST_DATABASE_URL not set — Postgres integration tests "
            "(CI sets this via the postgres service container)"
        )
    engine = create_async_engine(url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as sess:
        yield sess
        await sess.rollback()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


async def test_upsert_movie_insert_and_overwrite(session: AsyncSession) -> None:
    m1 = await crud.upsert_movie(
        session,
        code="101",
        title="One",
        file_id="file-a",
        channel_message_id=1,
        added_by=42,
    )
    await session.commit()
    assert m1.code == "101"
    assert m1.title == "One"

    m2 = await crud.upsert_movie(
        session,
        code="101",
        title="Two",
        file_id="file-b",
        channel_message_id=2,
        added_by=43,
    )
    await session.commit()
    assert m2.title == "Two"
    assert m2.file_id == "file-b"
    assert await crud.count_movies(session) == 1


async def test_upsert_user_activity_increments(session: AsyncSession) -> None:
    u1 = await crud.upsert_user_activity(session, 999001)
    await session.commit()
    assert u1.request_count == 1

    u2 = await crud.upsert_user_activity(session, 999001)
    await session.commit()
    assert u2.request_count == 2


async def test_ensure_user_sets_language_and_does_not_overwrite(
    session: AsyncSession,
) -> None:
    u1 = await crud.ensure_user(session, 888001, "en")
    await session.commit()
    assert u1.language_code == "en"
    assert u1.request_count == 0

    u2 = await crud.ensure_user(session, 888001, "uz")
    await session.commit()
    assert u2.language_code == "en"
    assert u2.request_count == 0

    u3 = await crud.set_user_language(session, 888001, "uz")
    await session.commit()
    assert u3.language_code == "uz"


async def test_ensure_user_unsupported_language_falls_back(
    session: AsyncSession,
) -> None:
    u1 = await crud.ensure_user(session, 888002, "fr")
    await session.commit()
    assert u1.language_code == "uz"


async def test_concurrent_movie_upserts(session: AsyncSession) -> None:
    """Two concurrent first-inserts for the same code must not raise."""
    url = _db_url()
    assert url
    engine = session.bind
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def one(n: int) -> None:
        async with factory() as s:
            await crud.upsert_movie(
                s,
                code="777",
                title=f"T{n}",
                file_id=f"f{n}",
                channel_message_id=n,
                added_by=n,
            )
            await s.commit()

    await asyncio.gather(one(1), one(2), one(3))
    assert await crud.count_movies(session) == 1


async def test_list_movies_window_count(session: AsyncSession) -> None:
    for i in range(3):
        await crud.upsert_movie(
            session,
            code=str(200 + i),
            title=None,
            file_id=f"f{i}",
            channel_message_id=i,
            added_by=1,
        )
    await session.commit()
    page, total = await crud.list_movies_paginated(session, page=0, per_page=2)
    assert total == 3
    assert len(page) == 2


async def test_delete_movie_second_call_is_not_found(session: AsyncSession) -> None:
    await crud.upsert_movie(
        session,
        code="301",
        title="Gone",
        file_id="file-del",
        channel_message_id=1,
        added_by=1,
    )
    await session.commit()
    assert await crud.delete_movie(session, "301") is True
    await session.commit()
    assert await crud.delete_movie(session, "301") is False
    assert await crud.get_movie_by_code(session, "301") is None
