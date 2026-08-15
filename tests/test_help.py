"""Tests for /help and Telegram command-menu registration."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from aiogram.types import BotCommandScopeChat, BotCommandScopeDefault
from bot.commands import admin_specs, as_bot_commands, format_help_text, user_specs
from bot.handlers import user as user_handlers
from bot.locales import TEXTS


def test_format_help_user_omits_admin_commands() -> None:
    text = format_help_text(TEXTS, is_admin=False)
    assert "/start" in text
    assert "/help" in text
    assert "/language" in text
    assert "/list_codes" not in text
    assert "/delete_code" not in text
    assert "/stats" not in text
    assert "/auditlog" not in text
    assert "/cancel" not in text
    assert "/broadcast" not in text
    assert TEXTS.HELP_ADMIN_HEADER not in text


def test_format_help_admin_includes_admin_commands() -> None:
    text = format_help_text(TEXTS, is_admin=True)
    assert "/start" in text
    assert "/help" in text
    assert "/list_codes" in text
    assert "/delete_code" in text
    assert "/stats" in text
    assert "/auditlog" in text
    assert "/cancel" in text
    assert "/broadcast" in text
    assert TEXTS.HELP_ADMIN_HEADER in text


@pytest.mark.asyncio
async def test_cmd_help_regular_user(monkeypatch: pytest.MonkeyPatch) -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=999)

    safe = AsyncMock()
    monkeypatch.setattr(user_handlers, "safe_answer", safe)
    await user_handlers.cmd_help(message)

    args, kwargs = safe.await_args
    body = args[1]
    assert "/start" in body
    assert "/list_codes" not in body
    assert kwargs.get("parse_mode") == "HTML"


@pytest.mark.asyncio
async def test_cmd_help_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=111)

    safe = AsyncMock()
    monkeypatch.setattr(user_handlers, "safe_answer", safe)
    await user_handlers.cmd_help(message)

    args, _kwargs = safe.await_args
    body = args[1]
    assert "/list_codes" in body
    assert "/auditlog" in body


@pytest.mark.asyncio
async def test_register_bot_commands_scopes() -> None:
    from bot import __main__ as main_mod

    bot = AsyncMock()
    await main_mod.register_bot_commands(bot)

    # (None, en, ru, uz) × (default scope + one admin chat)
    assert bot.set_my_commands.await_count == 8

    default_none = next(
        call
        for call in bot.set_my_commands.await_args_list
        if isinstance(call.kwargs["scope"], BotCommandScopeDefault)
        and call.kwargs.get("language_code") is None
    )
    default_names = {cmd.command for cmd in default_none.args[0]}
    assert default_names == {spec.command for spec in user_specs()}
    assert "list_codes" not in default_names

    admin_none = next(
        call
        for call in bot.set_my_commands.await_args_list
        if isinstance(call.kwargs["scope"], BotCommandScopeChat)
        and call.kwargs.get("language_code") is None
    )
    admin_names = {cmd.command for cmd in admin_none.args[0]}
    expected = {spec.command for spec in user_specs() + admin_specs()}
    assert admin_names == expected
    assert "list_codes" in admin_names
    assert admin_none.kwargs["scope"].chat_id == 111


def test_as_bot_commands_uses_texts_descriptions() -> None:
    cmds = as_bot_commands(user_specs(), TEXTS)
    by_name = {c.command: c.description for c in cmds}
    assert by_name["help"] == TEXTS.CMD_HELP_DESC
    assert by_name["start"] == TEXTS.CMD_START_DESC
