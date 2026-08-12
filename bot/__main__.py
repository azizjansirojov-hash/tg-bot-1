"""
Bot entrypoint.

Supports two run modes controlled by BOT_MODE:
  - polling  — local development (long polling)
  - webhook  — production (aiohttp HTTP server + setWebhook)
"""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.base import BaseStorage
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web
from sqlalchemy import text

from bot.config import get_settings
from bot.db.base import dispose_engine, get_engine, get_session_factory
from bot.handlers import register_routers
from bot.logging_setup import setup_logging
from bot.middlewares.db import DbSessionMiddleware
from bot.middlewares.rate_limit import (
    MemoryRateLimitBackend,
    RateLimitMiddleware,
    RedisRateLimitBackend,
)

logger = logging.getLogger(__name__)

# Kept alive for the process lifetime when USE_REDIS=true.
_redis_client: object | None = None


async def _check_database() -> None:
    """Fail fast if PostgreSQL is unreachable."""
    engine = get_engine()
    async with engine.connect() as conn:
        # Static SQL only — no user input, no string concatenation.
        await conn.execute(text("SELECT 1"))
    logger.info("Database connection OK")


async def healthz_handler(_request: web.Request) -> web.Response:
    """
    Lightweight readiness probe for webhook deployments.

    Performs a DB ping (SELECT 1) and returns 200 or 503.
    """
    try:
        engine = get_engine()
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return web.json_response({"status": "ok"}, status=200)
    except Exception:
        logger.exception("Health check failed")
        return web.json_response({"status": "unavailable"}, status=503)


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
    dp.update.middleware(_build_rate_limit_middleware())
    dp.update.middleware(DbSessionMiddleware())
    register_routers(dp)
    return dp


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

    await _check_database()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = _build_dispatcher()

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
