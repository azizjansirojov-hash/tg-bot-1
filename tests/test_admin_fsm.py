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
