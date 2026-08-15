"""Admin broadcast: permissions, confirm step, flood handling, audit."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter
from aiogram.methods import SendMessage
from bot.filters.admin import IsAdmin
from bot.handlers import admin as admin_handlers
from bot.handlers import user as user_handlers
from bot.locales import TEXTS
from bot.middlewares.rate_limit import MemoryRateLimitBackend, RateLimitMiddleware
from bot.services.broadcast import send_broadcast
from bot.states.admin_broadcast import AdminBroadcast


def _retry_after(chat_id: int, seconds: int) -> TelegramRetryAfter:
    return TelegramRetryAfter(
        method=SendMessage(chat_id=chat_id, text="x"),
        message="flood",
        retry_after=seconds,
    )


def _forbidden(chat_id: int) -> TelegramForbiddenError:
    return TelegramForbiddenError(
        method=SendMessage(chat_id=chat_id, text="x"),
        message="Forbidden: bot was blocked by the user",
    )


@pytest.mark.asyncio
async def test_is_admin_rejects_non_admin() -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=999)
    assert await IsAdmin()(message) is False


@pytest.mark.asyncio
async def test_non_admin_broadcast_denied(monkeypatch: pytest.MonkeyPatch) -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=999)
    safe = AsyncMock()
    monkeypatch.setattr(user_handlers, "safe_answer", safe)
    await user_handlers.admin_commands_denied(message)
    args, _kwargs = safe.await_args
    assert args[1] == TEXTS.ADMIN_ONLY


@pytest.mark.asyncio
async def test_broadcast_receive_text_does_not_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = MagicMock()
    message.text = "Hello everyone"
    message.from_user = MagicMock(id=111)
    state = AsyncMock()
    session = AsyncMock()
    monkeypatch.setattr(
        admin_handlers.crud, "count_broadcast_recipients", AsyncMock(return_value=3)
    )
    send = AsyncMock()
    monkeypatch.setattr(admin_handlers, "send_broadcast", send)
    safe = AsyncMock()
    monkeypatch.setattr(admin_handlers, "safe_answer", safe)

    await admin_handlers.broadcast_receive_text(message, state, session)

    send.assert_not_awaited()
    state.set_state.assert_awaited_with(AdminBroadcast.confirming)
    body = safe.await_args.args[1]
    assert "3" in body


@pytest.mark.asyncio
async def test_broadcast_confirm_no_does_not_send(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    callback = MagicMock()
    callback.data = "broadcast:no"
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    callback.from_user = MagicMock(id=111)
    state = AsyncMock()
    session = AsyncMock()
    send = AsyncMock()
    monkeypatch.setattr(admin_handlers, "send_broadcast", send)

    await admin_handlers.broadcast_confirm_callback(callback, state, session)

    send.assert_not_awaited()
    state.clear.assert_awaited()


@pytest.mark.asyncio
async def test_broadcast_confirm_yes_sends_and_writes_audit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bot.services.broadcast import BroadcastResult

    callback = MagicMock()
    callback.data = "broadcast:yes"
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    callback.from_user = MagicMock(id=111)
    callback.bot = AsyncMock()
    state = AsyncMock()
    state.get_data = AsyncMock(
        return_value={admin_handlers.FSM_BROADCAST_TEXT: "hi"}
    )
    session = AsyncMock()

    monkeypatch.setattr(
        admin_handlers.crud,
        "list_broadcast_recipient_ids",
        AsyncMock(return_value=[1, 2]),
    )
    monkeypatch.setattr(admin_handlers, "release_session", AsyncMock())
    result = BroadcastResult(
        attempted=2,
        succeeded=2,
        failed_blocked=0,
        failed_other=0,
        duration_ms=40,
        blocked_ids=[],
    )
    monkeypatch.setattr(
        admin_handlers, "send_broadcast", AsyncMock(return_value=result)
    )

    audit_session = AsyncMock()
    audit_session.__aenter__ = AsyncMock(return_value=audit_session)
    audit_session.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(
        admin_handlers, "get_session_factory", lambda: lambda: audit_session
    )
    write_audit = AsyncMock()
    monkeypatch.setattr(admin_handlers.crud, "write_audit_log", write_audit)
    monkeypatch.setattr(admin_handlers.crud, "mark_users_inactive", AsyncMock())

    await admin_handlers.broadcast_confirm_callback(callback, state, session)

    admin_handlers.send_broadcast.assert_awaited()
    write_audit.assert_awaited()
    kwargs = write_audit.await_args.kwargs
    assert kwargs["action"] == "broadcast"
    details = json.loads(kwargs["details"])
    assert details["attempted"] == 2
    assert details["succeeded"] == 2
    assert "hi" not in kwargs["details"]


@pytest.mark.asyncio
async def test_retry_after_pauses_and_resumes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    slept: list[float] = []

    async def fake_sleep(seconds: float) -> None:
        slept.append(seconds)

    monkeypatch.setattr("bot.services.broadcast.asyncio.sleep", fake_sleep)

    bot = AsyncMock()
    bot.send_message = AsyncMock(
        side_effect=[_retry_after(1, 2), None]
    )
    result = await send_broadcast(bot, [1], "hello", sends_per_second=100)
    assert result.succeeded == 1
    assert result.failed_other == 0
    assert 2 in slept
    assert bot.send_message.await_count == 2


@pytest.mark.asyncio
async def test_forbidden_does_not_stop_batch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def fake_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr("bot.services.broadcast.asyncio.sleep", fake_sleep)

    bot = AsyncMock()

    async def send_side_effect(*, chat_id: int, text: str, parse_mode: object) -> None:
        if chat_id == 2:
            raise _forbidden(2)

    bot.send_message = AsyncMock(side_effect=send_side_effect)
    result = await send_broadcast(bot, [1, 2, 3], "hello", sends_per_second=100)
    assert result.attempted == 3
    assert result.succeeded == 2
    assert result.failed_blocked == 1
    assert result.blocked_ids == [2]


@pytest.mark.asyncio
async def test_broadcast_command_cooldown() -> None:
    from aiogram.types import Update

    backend = MemoryRateLimitBackend()
    mw = RateLimitMiddleware(backend=backend)
    handler = AsyncMock(return_value="ok")

    message = MagicMock()
    message.text = "/broadcast"
    message.from_user = MagicMock(id=111, language_code="uz")
    message.answer = AsyncMock()

    update = MagicMock(spec=Update)
    update.message = message
    update.callback_query = None
    update.edited_message = None

    first = await mw(handler, update, {})
    assert first == "ok"
    assert handler.await_count == 1

    second = await mw(handler, update, {})
    assert second is None
    assert handler.await_count == 1
    message.answer.assert_awaited()
