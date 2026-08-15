"""Per-user rate limiting / anti-flood middleware (memory or Redis)."""

from __future__ import annotations

import logging
import time
import uuid
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from bot.config import get_settings
from bot.constants import CODE_RE
from bot.locales import get_texts
from bot.locales.lookup import load_stored_language

logger = logging.getLogger(__name__)


class RateLimitBackend(Protocol):
    """Sliding-window hit tracking used by RateLimitMiddleware."""

    async def is_limited(
        self,
        key: str,
        *,
        window: int,
        max_requests: int,
    ) -> bool:
        """Return True if the key is over the limit (and record a hit if not)."""

    async def record_block(self, user_id: int) -> int:
        """Record a rate-limit block; return current block count in abuse window."""


class MemoryRateLimitBackend:
    """
    In-process sliding-window rate limiter.

    Evicts idle user keys after window trim and caps tracked users via
    RATE_LIMIT_MAX_TRACKED_USERS (LRU-ish: drop oldest idle keys).

    NOT safe across multiple bot replicas — see SECURITY_HARDENING_REPORT.md.
    """

    def __init__(self, max_tracked_users: int = 10_000) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._block_hits: dict[int, deque[float]] = defaultdict(deque)
        self._last_touch: dict[str, float] = {}
        self._max_tracked = max_tracked_users

    def _trim(self, hits: deque[float], window: int, now: float) -> None:
        while hits and now - hits[0] > window:
            hits.popleft()

    def _evict_if_needed(self, now: float, *, protect: str | None = None) -> None:
        # Drop empty hit deques (never drop the key currently being updated).
        empty_keys = [
            k for k, d in self._hits.items() if not d and k != protect
        ]
        for k in empty_keys:
            self._hits.pop(k, None)
            self._last_touch.pop(k, None)

        if len(self._hits) <= self._max_tracked:
            return

        # Evict oldest-touched keys until under the cap (skip protect).
        ordered = sorted(self._last_touch.items(), key=lambda item: item[1])
        overflow = len(self._hits) - self._max_tracked
        removed = 0
        for key, _ in ordered:
            if removed >= overflow:
                break
            if key == protect:
                continue
            self._hits.pop(key, None)
            self._last_touch.pop(key, None)
            removed += 1

    async def is_limited(
        self,
        key: str,
        *,
        window: int,
        max_requests: int,
    ) -> bool:
        now = time.monotonic()
        hits = self._hits[key]
        self._trim(hits, window, now)
        if len(hits) >= max_requests:
            self._last_touch[key] = now
            return True
        hits.append(now)
        self._last_touch[key] = now
        self._evict_if_needed(now, protect=key)
        return False

    async def record_block(self, user_id: int) -> int:
        settings = get_settings()
        now = time.monotonic()
        blocks = self._block_hits[user_id]
        window = settings.rate_limit_abuse_window_seconds
        self._trim(blocks, window, now)
        blocks.append(now)
        # Evict idle block maps opportunistically.
        idle = [
            uid
            for uid, d in self._block_hits.items()
            if not d or (d and now - d[-1] > window)
        ]
        for uid in idle:
            if uid != user_id and (
                not self._block_hits[uid]
                or now - self._block_hits[uid][-1] > window
            ):
                self._block_hits.pop(uid, None)
        return len(blocks)


# Atomic sliding window: trim + cardinality check + optional ZADD in one EVAL.
_RL_SLIDING_WINDOW_LUA = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local max_requests = tonumber(ARGV[3])
local member = ARGV[4]
redis.call('ZREMRANGEBYSCORE', key, 0, now - window)
local count = redis.call('ZCARD', key)
if count >= max_requests then
  redis.call('EXPIRE', key, window + 1)
  return 1
end
redis.call('ZADD', key, now, member)
redis.call('EXPIRE', key, window + 1)
return 0
"""


class RedisRateLimitBackend:
    """
    Redis sliding-window rate limiter using an atomic Lua script.

    Keys expire after the window so multi-replica deployments stay bounded.
    See SECURITY_HARDENING_REPORT.md.
    """

    def __init__(self, redis: Any) -> None:
        self._redis = redis
        self._limited_script = redis.register_script(_RL_SLIDING_WINDOW_LUA)

    async def is_limited(
        self,
        key: str,
        *,
        window: int,
        max_requests: int,
    ) -> bool:
        now = time.time()
        redis_key = f"rl:hits:{key}"
        member = f"{now}:{uuid.uuid4().hex}"
        result = await self._limited_script(
            keys=[redis_key],
            args=[now, window, max_requests, member],
        )
        return int(result) == 1

    async def record_block(self, user_id: int) -> int:
        settings = get_settings()
        now = time.time()
        window = settings.rate_limit_abuse_window_seconds
        redis_key = f"rl:blocks:{user_id}"
        pipe = self._redis.pipeline()
        pipe.zremrangebyscore(redis_key, 0, now - window)
        pipe.zadd(redis_key, {f"{now}": now})
        pipe.expire(redis_key, window + 1)
        pipe.zcard(redis_key)
        results = await pipe.execute()
        return int(results[3])


class RateLimitMiddleware(BaseMiddleware):
    """
    Two-layer sliding-window rate limiter.

    Layers
    ------
    1. **Global ceiling** — every update with a ``from_user``. Applies to
       everyone including admins.
    2. **Code-lookup limit** — digit-only movie codes; admins exempt.
    3. **Broadcast cooldown** — ``/broadcast`` for admins only
       (``BROADCAST_COOLDOWN_SECONDS``, default 300). Confirm callbacks
       are not limited by this layer.

    Abuse signal: WARNING when blocks exceed RATE_LIMIT_ABUSE_THRESHOLD
    within RATE_LIMIT_ABUSE_WINDOW_SECONDS (user_id + count only).

    Backend is MemoryRateLimitBackend by default, or RedisRateLimitBackend
    when USE_REDIS=true. Multi-replica deployments require Redis —
    see SECURITY_HARDENING_REPORT.md.
    """

    def __init__(self, backend: RateLimitBackend | None = None) -> None:
        settings = get_settings()
        self._backend: RateLimitBackend = backend or MemoryRateLimitBackend(
            max_tracked_users=settings.rate_limit_max_tracked_users,
        )
        self._abuse_warned_at: dict[int, float] = {}

    def _prune_abuse_warnings(self, now: float, window: int) -> None:
        """Drop last-warn timestamps older than the abuse window."""
        stale = [
            uid
            for uid, ts in self._abuse_warned_at.items()
            if now - ts >= window
        ]
        for uid in stale:
            del self._abuse_warned_at[uid]

    def _is_code_message(self, message: Message) -> bool:
        text = (message.text or "").strip()
        if not text or text.startswith("/"):
            return False
        return CODE_RE.fullmatch(text) is not None

    def _is_broadcast_command(self, message: Message) -> bool:
        text = (message.text or "").strip()
        if not text.startswith("/"):
            return False
        cmd = text.split()[0].split("@", 1)[0].lower()
        return cmd == "/broadcast"

    def _extract_user_and_message(
        self,
        event: TelegramObject,
    ) -> tuple[int | None, Message | None, CallbackQuery | None]:
        if isinstance(event, Update):
            if event.message and event.message.from_user:
                return event.message.from_user.id, event.message, None
            if event.callback_query and event.callback_query.from_user:
                return (
                    event.callback_query.from_user.id,
                    None,
                    event.callback_query,
                )
            if event.edited_message and event.edited_message.from_user:
                return event.edited_message.from_user.id, event.edited_message, None
            return None, None, None

        if isinstance(event, Message) and event.from_user:
            return event.from_user.id, event, None
        if isinstance(event, CallbackQuery) and event.from_user:
            return event.from_user.id, None, event
        return None, None, None

    async def _notify_limited(
        self,
        message: Message | None,
        callback: CallbackQuery | None,
        seconds: int,
    ) -> None:
        lang = None
        user_id: int | None = None
        if message is not None and message.from_user is not None:
            lang = message.from_user.language_code
            user_id = message.from_user.id
        elif callback is not None and callback.from_user is not None:
            lang = callback.from_user.language_code
            user_id = callback.from_user.id
        stored: str | None = None
        if user_id is not None:
            stored = await load_stored_language(user_id)
        text = get_texts(stored or lang).RATE_LIMITED.format(seconds=seconds)
        if message is not None:
            try:
                await message.answer(text)
            except Exception:
                logger.exception("Failed to send rate-limit notice")
            return
        if callback is not None:
            try:
                await callback.answer(text, show_alert=True)
            except Exception:
                logger.exception("Failed to answer rate-limit callback")

    async def _maybe_abuse_warn(self, user_id: int, block_count: int) -> None:
        settings = get_settings()
        now = time.monotonic()
        window = settings.rate_limit_abuse_window_seconds
        self._prune_abuse_warnings(now, window)
        if block_count < settings.rate_limit_abuse_threshold:
            return
        last_warn = self._abuse_warned_at.get(user_id, 0.0)
        if now - last_warn < window:
            return
        self._abuse_warned_at[user_id] = now
        logger.warning(
            "Rate-limit abuse signal user_id=%s block_count=%s window_seconds=%s",
            user_id,
            block_count,
            window,
        )

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        settings = get_settings()
        user_id, message, callback = self._extract_user_and_message(event)
        if user_id is None:
            return await handler(event, data)


        if await self._backend.is_limited(
            f"global:{user_id}",
            window=settings.rate_limit_global_window_seconds,
            max_requests=settings.rate_limit_global_max_requests,
        ):
            count = await self._backend.record_block(user_id)
            await self._maybe_abuse_warn(user_id, count)
            await self._notify_limited(
                message,
                callback,
                settings.rate_limit_global_window_seconds,
            )
            return None

        if (
            message is not None
            and self._is_code_message(message)
            and not settings.is_admin(user_id)
        ):
            if await self._backend.is_limited(
                f"code:{user_id}",
                window=settings.rate_limit_window_seconds,
                max_requests=settings.rate_limit_max_requests,
            ):
                count = await self._backend.record_block(user_id)
                await self._maybe_abuse_warn(user_id, count)
                await self._notify_limited(
                    message,
                    callback,
                    settings.rate_limit_window_seconds,
                )
                return None

        if (
            message is not None
            and self._is_broadcast_command(message)
            and settings.is_admin(user_id)
        ):
            if await self._backend.is_limited(
                f"broadcast:{user_id}",
                window=settings.broadcast_cooldown_seconds,
                max_requests=1,
            ):
                count = await self._backend.record_block(user_id)
                await self._maybe_abuse_warn(user_id, count)
                await self._notify_limited(
                    message,
                    callback,
                    settings.broadcast_cooldown_seconds,
                )
                return None

        return await handler(event, data)
