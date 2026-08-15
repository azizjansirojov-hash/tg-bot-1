"""Smoke tests: polling/webhook startup paths after the aiohttp upgrade."""

from __future__ import annotations

import asyncio
import socket
from unittest.mock import AsyncMock, MagicMock

import aiohttp
import pytest
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import ClientSession
from bot.config import WEBHOOK_SECRET_MIN_LENGTH, get_settings


def _free_port() -> int:
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = int(sock.getsockname()[1])
    sock.close()
    return port


def test_webhook_without_redis_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    from bot import __main__ as main_mod
    from bot.config import Settings

    secret = "a" * WEBHOOK_SECRET_MIN_LENGTH + "-ok-random"
    settings = Settings(
        **{
            "BOT_TOKEN": "1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxx",
            "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/db",
            "STORAGE_CHANNEL_ID": "-1001234567890",
            "ADMIN_IDS": "111",
            "BOT_MODE": "webhook",
            "WEBHOOK_URL": "https://example.com",
            "WEBHOOK_SECRET": secret,
            "USE_REDIS": "false",
        }
    )  # type: ignore[arg-type]
    with caplog.at_level("WARNING", logger="bot.__main__"):
        main_mod._warn_if_webhook_without_redis(settings)
    assert "USE_REDIS=false" in caplog.text
    assert "BOT_MODE=webhook" in caplog.text
    version = aiohttp.__version__
    major_minor = ".".join(version.split(".")[:2])
    assert major_minor == "3.14", f"expected aiohttp 3.14.x, got {version}"


def test_build_dispatcher_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    from bot.db import base as db_base

    monkeypatch.setattr(db_base, "_engine", None)
    monkeypatch.setattr(db_base, "_session_factory", None)

    from bot import __main__ as main_mod

    dp = main_mod._build_dispatcher()
    assert isinstance(dp, Dispatcher)
    assert dp.storage is not None


@pytest.mark.asyncio
async def test_polling_mode_starts() -> None:
    from bot import __main__ as main_mod

    bot = AsyncMock()
    bot.delete_webhook = AsyncMock()
    dp = AsyncMock()
    dp.start_polling = AsyncMock()
    dp.resolve_used_update_types = MagicMock(return_value=["message"])

    await main_mod.run_polling(bot, dp)

    bot.delete_webhook.assert_awaited()
    dp.start_polling.assert_awaited()


class _FakeConn:
    async def execute(self, *_args: object, **_kwargs: object) -> None:
        return None

    async def __aenter__(self) -> _FakeConn:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class _FakeEngine:
    def connect(self) -> _FakeConn:
        return _FakeConn()


@pytest.mark.asyncio
async def test_webhook_mode_starts(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "a" * WEBHOOK_SECRET_MIN_LENGTH + "-ok-random"
    port = _free_port()
    monkeypatch.setenv("BOT_MODE", "webhook")
    monkeypatch.setenv("WEBHOOK_URL", "https://example.com")
    monkeypatch.setenv("WEBHOOK_SECRET", secret)
    monkeypatch.setenv("PORT", str(port))
    get_settings.cache_clear()

    from bot import __main__ as main_mod

    monkeypatch.setattr(main_mod, "get_engine", lambda: _FakeEngine())

    bot = AsyncMock()
    bot.set_webhook = AsyncMock()
    bot.delete_webhook = AsyncMock()
    dp = Dispatcher(storage=MemoryStorage())

    task = asyncio.create_task(main_mod.run_webhook(bot, dp))
    try:
        for _ in range(50):
            await asyncio.sleep(0.05)
            if bot.set_webhook.await_count:
                break
        bot.set_webhook.assert_awaited()

        last_error: Exception | None = None
        for _ in range(50):
            try:
                async with ClientSession() as session:
                    async with session.get(
                        f"http://127.0.0.1:{port}/healthz"
                    ) as resp:
                        assert resp.status == 200
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                await asyncio.sleep(0.05)
        if last_error is not None:
            raise last_error
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        get_settings.cache_clear()
