"""Application configuration loaded from environment variables."""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field, PrivateAttr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Minimum length for WEBHOOK_SECRET when BOT_MODE=webhook.
WEBHOOK_SECRET_MIN_LENGTH = 32

# Reject these exact values (case-insensitive) even if long enough.
_WEAK_WEBHOOK_SECRETS = frozenset(
    {
        "change-me-to-a-long-random-string",
        "changeme",
        "change-me",
        "secret",
        "password",
        "webhook_secret",
        "your-webhook-secret",
        "replace-me",
        "replace-with-a-long-random-secret-at-least-32-chars",
        "example",
        "test",
        "testing",
        "12345678901234567890123456789012",
    }
)


class Settings(BaseSettings):
    """Runtime settings. Required fields fail fast on startup if missing."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
    )

    bot_token: str = Field(..., validation_alias="BOT_TOKEN")
    database_url: str = Field(..., validation_alias="DATABASE_URL")
    storage_channel_id: int = Field(..., validation_alias="STORAGE_CHANNEL_ID")
    # Comma-separated string — keep as str so settings does not JSON-decode it.
    admin_ids_csv: str = Field(..., validation_alias="ADMIN_IDS")

    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    bot_mode: Literal["polling", "webhook"] = Field(
        default="polling",
        validation_alias="BOT_MODE",
    )

    webhook_url: str | None = Field(default=None, validation_alias="WEBHOOK_URL")
    webhook_path: str = Field(default="/webhook", validation_alias="WEBHOOK_PATH")
    webhook_secret: str | None = Field(default=None, validation_alias="WEBHOOK_SECRET")
    port: int = Field(default=8080, validation_alias="PORT")

    # Strict limit for digit-only movie-code lookups (non-admins only).
    rate_limit_max_requests: int = Field(
        default=5,
        validation_alias="RATE_LIMIT_MAX_REQUESTS",
    )
    rate_limit_window_seconds: int = Field(
        default=60,
        validation_alias="RATE_LIMIT_WINDOW_SECONDS",
    )

    # Global ceiling for ALL update types (applies to everyone, including admins).
    rate_limit_global_max_requests: int = Field(
        default=60,
        validation_alias="RATE_LIMIT_GLOBAL_MAX_REQUESTS",
    )
    rate_limit_global_window_seconds: int = Field(
        default=60,
        validation_alias="RATE_LIMIT_GLOBAL_WINDOW_SECONDS",
    )

    # Abuse signal: WARNING when a user is blocked this many times in the window.
    rate_limit_abuse_threshold: int = Field(
        default=10,
        validation_alias="RATE_LIMIT_ABUSE_THRESHOLD",
    )
    rate_limit_abuse_window_seconds: int = Field(
        default=300,
        validation_alias="RATE_LIMIT_ABUSE_WINDOW_SECONDS",
    )
    # Cap in-memory rate-limit maps (ignored when USE_REDIS=true).
    rate_limit_max_tracked_users: int = Field(
        default=10_000,
        validation_alias="RATE_LIMIT_MAX_TRACKED_USERS",
    )

    # Async SQLAlchemy pool tuning (prevents connection exhaustion under load).
    db_pool_size: int = Field(default=5, validation_alias="DB_POOL_SIZE")
    db_max_overflow: int = Field(default=10, validation_alias="DB_MAX_OVERFLOW")
    db_pool_timeout: int = Field(default=30, validation_alias="DB_POOL_TIMEOUT")
    db_pool_recycle: int = Field(default=1800, validation_alias="DB_POOL_RECYCLE")

    # Shared FSM + rate-limit state for multi-replica deployments.
    use_redis: bool = Field(default=False, validation_alias="USE_REDIS")
    redis_url: str | None = Field(
        default="redis://localhost:6379/0",
        validation_alias="REDIS_URL",
    )

    _admin_ids: list[int] = PrivateAttr(default_factory=list)

    @model_validator(mode="after")
    def parse_admin_ids(self) -> Settings:
        parts = [part.strip() for part in self.admin_ids_csv.split(",") if part.strip()]
        if not parts:
            raise ValueError("ADMIN_IDS must contain at least one Telegram user ID")
        try:
            self._admin_ids = [int(part) for part in parts]
        except ValueError as exc:
            raise ValueError(
                "ADMIN_IDS must be a comma-separated list of integers"
            ) from exc
        return self

    @model_validator(mode="after")
    def validate_redis_config(self) -> Settings:
        if self.use_redis and not self.redis_url:
            raise ValueError("USE_REDIS=true requires REDIS_URL to be set")
        return self

    @property
    def admin_ids(self) -> list[int]:
        return self._admin_ids

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        if not value.startswith("postgresql+asyncpg://"):
            raise ValueError(
                "DATABASE_URL must use the asyncpg driver, e.g. "
                "postgresql+asyncpg://user:pass@host:5432/dbname"
            )
        return value

    @field_validator("bot_token")
    @classmethod
    def validate_bot_token(cls, value: str) -> str:
        if ":" not in value or len(value) < 20:
            raise ValueError("BOT_TOKEN looks invalid")
        return value

    @staticmethod
    def _validate_webhook_secret_value(secret: str) -> None:
        """Fail fast on missing strength: length and known-weak defaults."""
        if len(secret) < WEBHOOK_SECRET_MIN_LENGTH:
            raise ValueError(
                f"WEBHOOK_SECRET must be at least {WEBHOOK_SECRET_MIN_LENGTH} "
                f"characters long (got {len(secret)})"
            )
        if secret.lower() in _WEAK_WEBHOOK_SECRETS:
            raise ValueError(
                "WEBHOOK_SECRET is a known weak/default value; "
                "set a long random secret (at least "
                f"{WEBHOOK_SECRET_MIN_LENGTH} characters)"
            )

    def validate_webhook_config(self) -> None:
        """Ensure webhook settings are present/strong when BOT_MODE=webhook."""
        if self.bot_mode != "webhook":
            return
        missing: list[str] = []
        if not self.webhook_url:
            missing.append("WEBHOOK_URL")
        if not self.webhook_secret:
            missing.append("WEBHOOK_SECRET")
        if missing:
            raise ValueError(
                "Webhook mode requires these environment variables: "
                + ", ".join(missing)
            )
        # webhook_secret is guaranteed non-empty here.
        self._validate_webhook_secret_value(self.webhook_secret)  # type: ignore[arg-type]

    @property
    def webhook_full_url(self) -> str:
        """Full webhook endpoint URL registered with Telegram."""
        if not self.webhook_url:
            raise ValueError("WEBHOOK_URL is not set")
        base = self.webhook_url.rstrip("/")
        path = (
            self.webhook_path
            if self.webhook_path.startswith("/")
            else f"/{self.webhook_path}"
        )
        return f"{base}{path}"

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.admin_ids


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings instance (fails fast if env is incomplete)."""
    settings = Settings()  # type: ignore[call-arg]
    settings.validate_webhook_config()
    return settings
