"""Admin FSM / title validation unit tests (mocked Telegram + FSM)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from bot.constants import TITLE_MAX_LEN
from bot.handlers import admin as admin_handlers
from bot.states.admin_add import AdminAddMovie


@pytest.mark.asyncio
async def test_title_too_long_stays_in_waiting_for_title(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = MagicMock()
    message.text = "x" * (TITLE_MAX_LEN + 1)
    message.from_user = MagicMock(id=1)

    state = AsyncMock()
    state.get_data = AsyncMock(
        return_value={
            admin_handlers.FSM_CODE: "102",
            admin_handlers.FSM_FILE_ID: "fid",
            admin_handlers.FSM_CHANNEL_MSG_ID: 9,
        }
    )

    safe = AsyncMock()
    monkeypatch.setattr(admin_handlers, "safe_answer", safe)
    await admin_handlers.admin_receive_title(message, state)

    safe.assert_awaited()
    # Must not advance state or clear on too-long title.
    state.set_state.assert_not_awaited()
    state.clear.assert_not_awaited()


@pytest.mark.asyncio
async def test_title_ok_moves_to_confirming_save(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = MagicMock()
    message.text = "My Film"
    message.from_user = MagicMock(id=1)

    state = AsyncMock()
    state.get_data = AsyncMock(
        return_value={
            admin_handlers.FSM_CODE: "102",
            admin_handlers.FSM_FILE_ID: "fid",
            admin_handlers.FSM_CHANNEL_MSG_ID: 9,
        }
    )

    safe = AsyncMock()
    monkeypatch.setattr(admin_handlers, "safe_answer", safe)
    await admin_handlers.admin_receive_title(message, state)

    state.update_data.assert_awaited()
    state.set_state.assert_awaited_with(AdminAddMovie.confirming_save)
    safe.assert_awaited()


@pytest.mark.asyncio
async def test_overwrite_callback_uses_fsm_code_not_payload() -> None:
    callback = MagicMock()
    callback.data = "overwrite:yes"
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    callback.from_user = MagicMock(id=99)

    state = AsyncMock()
    state.get_data = AsyncMock(return_value={admin_handlers.FSM_CODE: "555"})

    await admin_handlers.admin_overwrite_callback(callback, state)

    state.update_data.assert_awaited_with({admin_handlers.FSM_OVERWRITE: True})
    state.set_state.assert_awaited_with(AdminAddMovie.waiting_for_title)
    # Message should mention FSM code 555 (escaped).
    args, kwargs = callback.message.edit_text.await_args
    assert "555" in args[0]


@pytest.mark.asyncio
async def test_save_cancelled_clears_state() -> None:
    callback = MagicMock()
    callback.data = "save:no"
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    callback.from_user = MagicMock(id=99)

    state = AsyncMock()
    session = AsyncMock()

    await admin_handlers.admin_save_callback(callback, state, session)

    state.clear.assert_awaited()
    session.execute.assert_not_called()


@pytest.mark.asyncio
async def test_delete_callback_already_gone_is_not_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    callback = MagicMock()
    callback.data = "delete:yes:102"
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    callback.from_user = MagicMock(id=7)
    session = AsyncMock()

    monkeypatch.setattr(
        admin_handlers.crud, "delete_movie", AsyncMock(return_value=False)
    )
    await admin_handlers.delete_code_callback(callback, session)

    args, kwargs = callback.message.edit_text.await_args
    assert "102" in args[0]
    from bot.locales import TEXTS

    assert args[0] == TEXTS.ADMIN_DELETE_ALREADY_GONE.format(code="102")


def test_page_count() -> None:
    assert admin_handlers.page_count(0) == 1
    assert admin_handlers.page_count(10) == 1
    assert admin_handlers.page_count(11) == 2


@pytest.mark.asyncio
async def test_cancel_clears_waiting_for_code_not_swallowed_as_code() -> None:
    """Slash commands must not be handled as movie codes during add-movie FSM."""
    from datetime import datetime, timezone

    from aiogram import Bot, Dispatcher
    from aiogram.client.session.base import BaseSession
    from aiogram.enums import ChatType
    from aiogram.fsm.storage.base import StorageKey
    from aiogram.fsm.storage.memory import MemoryStorage
    from aiogram.methods import TelegramMethod
    from aiogram.types import Chat, Message, Update, User
    from bot.handlers.admin import router
    from bot.states.admin_add import AdminAddMovie

    class _SilentSession(BaseSession):
        async def close(self) -> None:
            return None

        async def stream_content(self, *args, **kwargs):  # type: ignore[no-untyped-def]
            raise NotImplementedError

        async def make_request(self, bot: Bot, method: TelegramMethod, timeout=None):  # type: ignore[no-untyped-def]
            return True

    storage = MemoryStorage()
    dp = Dispatcher(storage=storage)
    bot = Bot(token="1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxx", session=_SilentSession())
    try:
        dp.include_router(router)
        key = StorageKey(bot_id=bot.id, chat_id=111, user_id=111)
        await storage.set_state(key, AdminAddMovie.waiting_for_code)
        await storage.set_data(key, {"file_id": "fid", "channel_message_id": 1})

        msg = Message(
            message_id=1,
            date=datetime.now(timezone.utc),
            chat=Chat(id=111, type=ChatType.PRIVATE),
            from_user=User(id=111, is_bot=False, first_name="Admin"),
            text="/cancel",
        )
        await dp.feed_update(bot, Update(update_id=1, message=msg))
        assert await storage.get_state(key) is None
    finally:
        router._parent_router = None
        await bot.session.close()
