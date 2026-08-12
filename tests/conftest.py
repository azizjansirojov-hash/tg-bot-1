"""Shared pytest fixtures — set required env before Settings is loaded."""

from __future__ import annotations

import os

import pytest

# Ensure Settings() can construct in unit tests even without a local .env.
_DEFAULTS = {
    "BOT_TOKEN": "1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxx",
    "DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/tgbot",
    "STORAGE_CHANNEL_ID": "-1001234567890",
    "ADMIN_IDS": "111",
    "BOT_MODE": "polling",
    "USE_REDIS": "false",
}


@pytest.fixture(autouse=True)
def _env_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    for key, value in _DEFAULTS.items():
        monkeypatch.setenv(key, value)
    # Clear cached settings between tests.
    from bot.config import get_settings

    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def test_database_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL")
