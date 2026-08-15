"""
Bot entrypoint.

Supports two run modes controlled by BOT_MODE:
  - polling  — local development (long polling)
  - webhook  — production (aiohttp HTTP server + setWebhook)
"""

from __future__ import annotations

import asyncio
import logging
import time

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommandScopeChat, BotCommandScopeDefault, ErrorEvent
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from sqlalchemy import text

from bot.commands import admin_specs, as_bot_commands, user_specs
from bot.config import get_settings
from bot.db.base import dispose_engine, get_engine, get_session_factory
from bot.handlers import register_routers
from bot.locales import SUPPORTED_LANGUAGES, get_texts
from bot.locales.lookup import load_stored_language
from bot.logging_setup import setup_logging
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.locale import UserLocaleMiddleware, telegram_user_from_event
from bot.middlewares.rate_limit import (
    MemoryRateLimitBackend,
    RateLimitMiddleware,
    RedisRateLimitBackend,
)

logger = logging.getLogger(__name__)

# Kept alive for the process lifetime when USE_REDIS=true.
_redis_client: object | None = None

_WEBHOOK_NO_REDIS_WARNING = (
    "BOT_MODE=webhook with USE_REDIS=false: rate limiting and FSM storage "
    "are in-process only (MemoryStorage / in-memory maps). Running more than "
    "one bot replica will split rate limits and lose or duplicate FSM state. "
    "Set USE_REDIS=true and REDIS_URL before scaling out. "
    "Set BOT_REPLICA_COUNT>1 to fail fast if Redis is not enabled."
)


def _warn_if_webhook_without_redis(settings: object) -> None:
    """Loud warning when webhook mode uses in-process FSM / rate limits."""
    bot_mode = getattr(settings, "bot_mode", None)
    use_redis = getattr(settings, "use_redis", False)
    if bot_mode == "webhook" and not use_redis:
        logger.warning(_WEBHOOK_NO_REDIS_WARNING)


async def _check_database() -> None:
    """Fail fast if PostgreSQL is unreachable."""
    engine = get_engine()
    async with engine.connect() as conn:
        # Static SQL only — no user input, no string concatenation.
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection OK")


# Reuse the last DB probe for this many seconds (unauthenticated /healthz).
HEALTHZ_DB_CACHE_SECONDS = 5.0
_healthz_cache: tuple[float, int, dict[str, str]] | None = None
_healthz_lock: asyncio.Lock | None = None


def _healthz_lock_get() -> asyncio.Lock:
    global _healthz_lock
    if _healthz_lock is None:
        _healthz_lock = asyncio.Lock()
    return _healthz_lock


def reset_healthz_cache() -> None:
    """Test helper: drop the cached readiness result."""
    global _healthz_cache
    _healthz_cache = None


async def livez_handler(_request: web.Request) -> web.Response:
    """Liveness: process is up. No database call."""
    return web.json_response({"status": "ok"}, status=200)


async def healthz_handler(_request: web.Request) -> web.Response:
    """
    Readiness probe for webhook deployments.

    Performs a DB ping (SELECT 1) at most once per HEALTHZ_DB_CACHE_SECONDS
    so an unauthenticated endpoint cannot stampede the connection pool.
    """
    global _healthz_cache
    now = time.monotonic()
    cached = _healthz_cache
    if cached is not None and now - cached[0] < HEALTHZ_DB_CACHE_SECONDS:
        return web.json_response(cached[2], status=cached[1])

    async with _healthz_lock_get():
        now = time.monotonic()
        cached = _healthz_cache
        if cached is not None and now - cached[0] < HEALTHZ_DB_CACHE_SECONDS:
            return web.json_response(cached[2], status=cached[1])
        try:
            engine = get_engine()
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            body, status = {"status": "ok"}, 200
        except Exception:
            logger.exception("Health check failed")
            body, status = {"status": "unavailable"}, 503
        _healthz_cache = (time.monotonic(), status, body)
        return web.json_response(body, status=status)


async def unhandled_error_handler(event: ErrorEvent) -> None:
    """Log uncaught handler errors and reply with a generic user-facing message."""
    update = event.update
    message = getattr(update, "message", None) or getattr(
        update, "edited_message", None
    )
    callback = getattr(update, "callback_query", None)
    user_id: int | None = None
    language_code: str | None = None
    from_user = telegram_user_from_event(update)
    if from_user is not None:
        user_id = from_user.id
        language_code = from_user.language_code
    elif message is not None and getattr(message, "from_user", None) is not None:
        user_id = message.from_user.id
        language_code = message.from_user.language_code
    elif callback is not None and getattr(callback, "from_user", None) is not None:
        user_id = callback.from_user.id
        language_code = callback.from_user.language_code

    logger.error(
        "Unhandled handler error user_id=%s update_id=%s exception=%s",
        user_id,
        getattr(update, "update_id", None),
        type(event.exception).__name__,
        exc_info=event.exception,
    )
    stored: str | None = None
    if user_id is not None:
        try:
            stored = await load_stored_language(user_id)
        except Exception:
            logger.exception(
                "Failed to load language in error handler user_id=%s",
                user_id,
            )
    error_text = get_texts(stored or language_code).GENERIC_ERROR
    try:
        if message is not None:
            await message.answer(error_text)
        elif callback is not None:
            await callback.answer(error_text, show_alert=True)
    except Exception:
        logger.exception(
            "Failed to notify user after unhandled error user_id=%s",
            user_id,
        )


def _build_fsm_storage() -> BaseStorage:
    """MemoryStorage by default; RedisStorage when USE_REDIS=true."""
    global _redis_client
    settings = get_settings()
    if not settings.use_redis:
        return MemoryStorage()

    from aiogram.fsm.storage.redis import RedisStorage
    from redis.asyncio import Redis

    assert settings.redis_url is not None
    _redis_client = Redis.from_url(settings.redis_url)
    logger.info("FSM storage: RedisStorage")
    return RedisStorage(redis=_redis_client)  # type: ignore[arg-type]


def _build_rate_limit_middleware() -> RateLimitMiddleware:
    """In-memory backend by default; Redis backend when USE_REDIS=true."""
    global _redis_client
    settings = get_settings()
    if not settings.use_redis:
        return RateLimitMiddleware(
            backend=MemoryRateLimitBackend(
                max_tracked_users=settings.rate_limit_max_tracked_users,
            )
        )

    from redis.asyncio import Redis

    if _redis_client is None:
        assert settings.redis_url is not None
        _redis_client = Redis.from_url(settings.redis_url)
    logger.info("Rate limit backend: Redis")
    return RateLimitMiddleware(backend=RedisRateLimitBackend(_redis_client))


def _build_dispatcher() -> Dispatcher:
    """Create dispatcher with FSM storage, middleware, and routers."""
    # Ensure session factory is ready before the first update.
    get_session_factory()

    dp = Dispatcher(storage=_build_fsm_storage())
    dp.errors.register(unhandled_error_handler)
    dp.update.middleware(_build_rate_limit_middleware())
    dp.update.middleware(DbSessionMiddleware())
    dp.update.middleware(UserLocaleMiddleware())
    register_routers(dp)
    return dp


async def register_bot_commands(bot: Bot) -> None:
    """Register the slash-command menu (default vs per-admin private chat)."""
    settings = get_settings()
    # None = Telegram fallback; then each supported client language.
    language_codes: tuple[str | None, ...] = (None, *sorted(SUPPORTED_LANGUAGES))
    for lang in language_codes:
        texts = get_texts(lang)
        user_cmds = as_bot_commands(user_specs(), texts)
        admin_cmds = as_bot_commands(user_specs() + admin_specs(), texts)
        await bot.set_my_commands(
            user_cmds,
            scope=BotCommandScopeDefault(),
            language_code=lang,
        )
        for admin_id in settings.admin_ids:
            await bot.set_my_commands(
                admin_cmds,
                scope=BotCommandScopeChat(chat_id=admin_id),
                language_code=lang,
            )
    logger.info(
        "Registered bot commands languages=%s admin_chats=%s",
        list(language_codes),
        len(settings.admin_ids),
    )


async def run_polling(bot: Bot, dp: Dispatcher) -> None:
    """Local development: long polling after clearing any existing webhook."""
    await bot.delete_webhook(drop_pending_updates=False)
    logger.info("Starting bot in polling mode")
    await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())


async def run_webhook(bot: Bot, dp: Dispatcher) -> None:
    """
    Production: register webhook with Telegram and serve updates over HTTPS.

    Railway/Render terminate TLS; this process listens on PORT with plain HTTP.
    SimpleRequestHandler validates X-Telegram-Bot-Api-Secret-Token against
    WEBHOOK_SECRET and rejects mismatches before any update processing.
    """
    settings = get_settings()
    settings.validate_webhook_config()

    await bot.set_webhook(
        url=settings.webhook_full_url,
        secret_token=settings.webhook_secret,
        drop_pending_updates=False,
        allowed_updates=dp.resolve_used_update_types(),
    )
    logger.info("Webhook set to %s", settings.webhook_full_url)

    app = web.Application()
    app.router.add_get("/livez", livez_handler)
    app.router.add_get("/healthz", healthz_handler)

    webhook_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.webhook_secret,
    )
    webhook_handler.register(app, path=settings.webhook_path)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=settings.port)
    await site.start()
    logger.info("Webhook HTTP server listening on 0.0.0.0:%s", settings.port)

    # Keep the process alive until cancelled (SIGTERM on deploy platforms).
    try:
        await asyncio.Event().wait()
    finally:
        await bot.delete_webhook(drop_pending_updates=False)
        await runner.cleanup()


async def main() -> None:
    settings = get_settings()
    setup_logging(settings.log_level)

    logger.info(
        "Booting bot mode=%s use_redis=%s storage_channel_configured=%s admin_count=%s",
        settings.bot_mode,
        settings.use_redis,
        bool(settings.storage_channel_id),
        len(settings.admin_ids),
    )

    _warn_if_webhook_without_redis(settings)

    await _check_database()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = _build_dispatcher()
    await register_bot_commands(bot)

    try:
        if settings.bot_mode == "webhook":
            await run_webhook(bot, dp)
        else:
            await run_polling(bot, dp)
    finally:
        await bot.session.close()
        if _redis_client is not None:
            close = getattr(_redis_client, "aclose", None) or getattr(
                _redis_client, "close", None
            )
            if close is not None:
                result = close()
                if asyncio.iscoroutine(result):
                    await result
        await dispose_engine()
        logger.info("Shutdown complete")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
