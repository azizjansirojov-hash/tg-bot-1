"""Non-admin videos: storage-channel forwards get ADMIN_ONLY; ordinary videos do not."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest
from aiogram import Bot, Dispatcher
from aiogram.client.session.base import BaseSession
from aiogram.enums import ChatType
from aiogram.fsm.storage.base import StorageKey
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.methods import TelegramMethod
from aiogram.types import (
    Chat,
    Message,
    MessageOriginChannel,
    Update,
    User,
    Video,
)
from bot.handlers import register_routers
from bot.handlers import user as user_handlers
from bot.locales import get_texts
from bot.middlewares.locale import UserLocaleMiddleware

STORAGE_CHANNEL_ID = -1001234567890
NON_ADMIN_ID = 999


class _SilentSession(BaseSession):
    async def close(self) -> None:
        return None

    async def stream_content(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        raise NotImplementedError

    async def make_request(self, bot: Bot, method: TelegramMethod, timeout=None):  # type: ignore[no-untyped-def]
        return True


def _video() -> Video:
    return Video(
        file_id="BAACAgIAAxkBAAIfakeFileIdForTests123456",
        file_unique_id="unique123",
        width=1280,
        height=720,
        duration=10,
    )


def _non_admin_user(*, language_code: str = "en") -> User:
    return User(
        id=NON_ADMIN_ID,
        is_bot=False,
        first_name="User",
        language_code=language_code,
    )


def _base_kwargs(user: User) -> dict[str, object]:
    return {
        "message_id": 1,
        "date": datetime.now(timezone.utc),
        "chat": Chat(id=NON_ADMIN_ID, type=ChatType.PRIVATE),
        "from_user": user,
        "video": _video(),
    }


@pytest.mark.asyncio
async def test_non_admin_storage_forward_gets_admin_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _non_admin_user(language_code="en")
    origin = MessageOriginChannel(
        type="channel",
        date=datetime.now(timezone.utc),
        chat=Chat(id=STORAGE_CHANNEL_ID, type=ChatType.CHANNEL, title="Storage"),
        message_id=777,
    )
    msg = Message(**_base_kwargs(user), forward_origin=origin)  # type: ignore[arg-type]

    safe = AsyncMock()
    monkeypatch.setattr(user_handlers, "safe_answer", safe)

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.update.middleware(UserLocaleMiddleware())
    register_routers(dp)
    bot = Bot(token="1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxx", session=_SilentSession())
    try:
        await dp.feed_update(bot, Update(update_id=1, message=msg))
        key = StorageKey(bot_id=bot.id, chat_id=NON_ADMIN_ID, user_id=NON_ADMIN_ID)
        assert await storage.get_state(key) is None
        safe.assert_awaited()
        args, _kwargs = safe.await_args
        assert args[1] == get_texts("en").ADMIN_ONLY
    finally:
        from bot.handlers.admin import router as admin_router
        from bot.handlers.user import router as user_router

        admin_router._parent_router = None
        user_router._parent_router = None
        await bot.session.close()


@pytest.mark.asyncio
async def test_non_admin_ordinary_video_is_not_admin_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    user = _non_admin_user(language_code="en")
    msg = Message(**_base_kwargs(user))  # type: ignore[arg-type]

    safe = AsyncMock()
    monkeypatch.setattr(user_handlers, "safe_answer", safe)

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    dp.update.middleware(UserLocaleMiddleware())
    register_routers(dp)
    bot = Bot(token="1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxx", session=_SilentSession())
    try:
        await dp.feed_update(bot, Update(update_id=1, message=msg))
        key = StorageKey(bot_id=bot.id, chat_id=NON_ADMIN_ID, user_id=NON_ADMIN_ID)
        assert await storage.get_state(key) is None
        for call in safe.await_args_list:
            assert call.args[1] != get_texts("en").ADMIN_ONLY
            assert call.args[1] != get_texts("uz").ADMIN_ONLY
    finally:
        from bot.handlers.admin import router as admin_router
        from bot.handlers.user import router as user_router

        admin_router._parent_router = None
        user_router._parent_router = None
        await bot.session.close()
