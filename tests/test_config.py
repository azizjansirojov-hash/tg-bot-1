"""Config validator tests (no real .env required)."""

from __future__ import annotations

import pytest
from bot.config import WEBHOOK_SECRET_MIN_LENGTH, Settings
from pydantic import ValidationError


def _base_kwargs(**overrides: object) -> dict:
    data: dict = {
        "BOT_TOKEN": "1234567890:AAHxxxxxxxxxxxxxxxxxxxxxxx",
        "DATABASE_URL": "postgresql+asyncpg://u:p@localhost:5432/db",
        "STORAGE_CHANNEL_ID": "-1001234567890",
        "ADMIN_IDS": "111,222",
        "BOT_MODE": "polling",
    }
    data.update(overrides)
    return data


def test_database_url_requires_asyncpg() -> None:
    with pytest.raises(ValidationError, match="asyncpg"):
        Settings(**_base_kwargs(DATABASE_URL="postgresql://u:p@localhost/db"))  # type: ignore[arg-type]


def test_admin_ids_parsed() -> None:
    s = Settings(**_base_kwargs())  # type: ignore[arg-type]
    assert s.admin_ids == [111, 222]
    assert s.is_admin(111)
    assert not s.is_admin(999)


def test_webhook_secret_too_short() -> None:
    s = Settings(
        **_base_kwargs(
            BOT_MODE="webhook",
            WEBHOOK_URL="https://example.com",
            WEBHOOK_SECRET="x" * (WEBHOOK_SECRET_MIN_LENGTH - 1),
        )
    )  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="at least"):
        s.validate_webhook_config()


def test_webhook_secret_weak_default() -> None:
    s = Settings(
        **_base_kwargs(
            BOT_MODE="webhook",
            WEBHOOK_URL="https://example.com",
            WEBHOOK_SECRET="replace-with-a-long-random-secret-at-least-32-chars",
        )
    )  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="weak"):
        s.validate_webhook_config()


def test_webhook_secret_ok() -> None:
    secret = "a" * WEBHOOK_SECRET_MIN_LENGTH + "-ok-random"
    s = Settings(
        **_base_kwargs(
            BOT_MODE="webhook",
            WEBHOOK_URL="https://example.com",
            WEBHOOK_SECRET=secret,
        )
    )  # type: ignore[arg-type]
    s.validate_webhook_config()
    assert s.webhook_full_url == "https://example.com/webhook"


def test_use_redis_requires_url() -> None:
    with pytest.raises(ValidationError, match="REDIS_URL"):
        Settings(**_base_kwargs(USE_REDIS=True, REDIS_URL=None))  # type: ignore[arg-type]


def test_replica_count_requires_redis() -> None:
    with pytest.raises(ValidationError, match="BOT_REPLICA_COUNT"):
        Settings(**_base_kwargs(BOT_REPLICA_COUNT=2, USE_REDIS=False))  # type: ignore[arg-type]


def test_replica_count_ok_with_redis() -> None:
    s = Settings(
        **_base_kwargs(BOT_REPLICA_COUNT=2, USE_REDIS=True, REDIS_URL="redis://localhost:6379/0")
    )  # type: ignore[arg-type]
    assert s.bot_replica_count == 2
    assert s.use_redis is True


def test_webhook_url_requires_https() -> None:
    secret = "a" * WEBHOOK_SECRET_MIN_LENGTH + "-ok-random"
    s = Settings(
        **_base_kwargs(
            BOT_MODE="webhook",
            WEBHOOK_URL="http://example.com",
            WEBHOOK_SECRET=secret,
        )
    )  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="https://"):
        s.validate_webhook_config()


def test_webhook_url_https_ok() -> None:
    secret = "a" * WEBHOOK_SECRET_MIN_LENGTH + "-ok-random"
    s = Settings(
        **_base_kwargs(
            BOT_MODE="webhook",
            WEBHOOK_URL="https://example.com",
            WEBHOOK_SECRET=secret,
        )
    )  # type: ignore[arg-type]
    s.validate_webhook_config()
    assert s.webhook_full_url == "https://example.com/webhook"


def test_bot_token_invalid() -> None:
    with pytest.raises(ValidationError, match="BOT_TOKEN"):
        Settings(**_base_kwargs(BOT_TOKEN="short"))  # type: ignore[arg-type]
