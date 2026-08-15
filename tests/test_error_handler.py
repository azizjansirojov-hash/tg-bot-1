"""Global dispatcher error handler tests."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from bot.locales import TEXTS
from bot.locales.en import TEXTS as EN_TEXTS


@pytest.mark.asyncio
async def test_unhandled_error_logs_and_replies_message(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bot import __main__ as main_mod

    monkeypatch.setattr(main_mod, "load_stored_language", AsyncMock(return_value=None))

    message = MagicMock()
    message.answer = AsyncMock()
    message.from_user = MagicMock(id=42)
    event = SimpleNamespace(
        exception=RuntimeError("admin db failed"),
        update=SimpleNamespace(
            update_id=7,
            message=message,
            edited_message=None,
            callback_query=None,
        ),
    )

    with caplog.at_level("ERROR", logger="bot.__main__"):
        await main_mod.unhandled_error_handler(event)  # type: ignore[arg-type]

    message.answer.assert_awaited_with(TEXTS.GENERIC_ERROR)
    assert "Unhandled handler error" in caplog.text
    assert "user_id=42" in caplog.text
    assert "RuntimeError" in caplog.text


@pytest.mark.asyncio
async def test_unhandled_error_answers_callback(
    caplog: pytest.LogCaptureFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bot import __main__ as main_mod

    monkeypatch.setattr(main_mod, "load_stored_language", AsyncMock(return_value=None))

    callback = MagicMock()
    callback.answer = AsyncMock()
    callback.from_user = MagicMock(id=9)
    event = SimpleNamespace(
        exception=ValueError("pagination failed"),
        update=SimpleNamespace(
            update_id=8,
            message=None,
            edited_message=None,
            callback_query=callback,
        ),
    )

    with caplog.at_level("ERROR", logger="bot.__main__"):
        await main_mod.unhandled_error_handler(event)  # type: ignore[arg-type]

    callback.answer.assert_awaited_with(TEXTS.GENERIC_ERROR, show_alert=True)
    assert "user_id=9" in caplog.text


@pytest.mark.asyncio
async def test_unhandled_error_uses_stored_english(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bot import __main__ as main_mod

    monkeypatch.setattr(main_mod, "load_stored_language", AsyncMock(return_value="en"))

    message = MagicMock()
    message.answer = AsyncMock()
    message.from_user = MagicMock(id=42, language_code="uz")
    event = SimpleNamespace(
        exception=RuntimeError("boom"),
        update=SimpleNamespace(
            update_id=9,
            message=message,
            edited_message=None,
            callback_query=None,
        ),
    )

    await main_mod.unhandled_error_handler(event)  # type: ignore[arg-type]

    message.answer.assert_awaited_with(EN_TEXTS.GENERIC_ERROR)


@pytest.mark.asyncio
async def test_unhandled_error_lookup_failure_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bot import __main__ as main_mod

    async def boom(_user_id: int) -> str | None:
        raise RuntimeError("lookup failed")

    monkeypatch.setattr(main_mod, "load_stored_language", boom)

    message = MagicMock()
    message.answer = AsyncMock()
    message.from_user = MagicMock(id=42, language_code="uz")
    event = SimpleNamespace(
        exception=RuntimeError("handler failed"),
        update=SimpleNamespace(
            update_id=10,
            message=message,
            edited_message=None,
            callback_query=None,
        ),
    )

    await main_mod.unhandled_error_handler(event)  # type: ignore[arg-type]

    message.answer.assert_awaited_with(TEXTS.GENERIC_ERROR)
