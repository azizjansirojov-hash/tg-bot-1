"""Rate-limit backend tests (memory + Lua fake + real Redis EVAL)."""

from __future__ import annotations

import asyncio
import os
import time
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from bot.middlewares.rate_limit import (
    _RL_SLIDING_WINDOW_LUA,
    MemoryRateLimitBackend,
    RedisRateLimitBackend,
)

_DEFAULT_TEST_REDIS_URL = "redis://localhost:6379/0"


def _test_redis_url() -> str:
    return (
        os.environ.get("TEST_REDIS_URL")
        or os.environ.get("REDIS_URL")
        or _DEFAULT_TEST_REDIS_URL
    )


@pytest.fixture
async def real_redis():
    """Yield a redis.asyncio client, or skip if Redis is not reachable."""
    from redis.asyncio import Redis

    url = _test_redis_url()
    client = Redis.from_url(url)
    try:
        await client.ping()
    except Exception as exc:
        await client.aclose()
        pytest.skip(
            f"Redis not reachable at {url} ({exc}). "
            "Start Redis (docker compose up -d redis) or set TEST_REDIS_URL."
        )
    yield client
    await client.aclose()


class _AtomicFakeRedis:
    """Minimal Redis stand-in: EVAL/register_script is serialized and atomic."""

    def __init__(self) -> None:
        self._zsets: dict[str, dict[str, float]] = {}
        self._lock = asyncio.Lock()

    def register_script(self, _script: str):
        async def _run(*, keys: list[str], args: list[object]) -> int:
            async with self._lock:
                key = keys[0]
                now = float(args[0])
                window = float(args[1])
                max_requests = int(args[2])
                member = str(args[3])
                zset = self._zsets.setdefault(key, {})
                cutoff = now - window
                for item, score in list(zset.items()):
                    if score <= cutoff:
                        del zset[item]
                if len(zset) >= max_requests:
                    return 1
                zset[member] = now
                return 0

        return _run


@pytest.mark.asyncio
async def test_memory_allows_under_limit() -> None:
    backend = MemoryRateLimitBackend(max_tracked_users=100)
    max_req = 5
    for i in range(max_req):
        limited = await backend.is_limited("code:1", window=60, max_requests=max_req)
        assert limited is False, f"request {i} should be allowed"
    assert await backend.is_limited("code:1", window=60, max_requests=max_req) is True


@pytest.mark.asyncio
async def test_memory_separate_keys() -> None:
    backend = MemoryRateLimitBackend(max_tracked_users=100)
    for _ in range(5):
        assert await backend.is_limited("global:1", window=60, max_requests=5) is False
    assert await backend.is_limited("global:1", window=60, max_requests=5) is True
    assert await backend.is_limited("global:2", window=60, max_requests=5) is False


@pytest.mark.asyncio
async def test_memory_eviction_cap() -> None:
    backend = MemoryRateLimitBackend(max_tracked_users=3)
    for i in range(5):
        await backend.is_limited(f"k:{i}", window=60, max_requests=10)
    assert len(backend._hits) <= 3


@pytest.mark.asyncio
async def test_record_block_count() -> None:
    backend = MemoryRateLimitBackend(max_tracked_users=100)
    c1 = await backend.record_block(42)
    c2 = await backend.record_block(42)
    assert c2 == c1 + 1


@pytest.mark.asyncio
async def test_redis_lua_does_not_overshoot_under_concurrency() -> None:
    backend = RedisRateLimitBackend(_AtomicFakeRedis())
    max_req = 5
    results = await asyncio.gather(
        *[
            backend.is_limited("code:1", window=60, max_requests=max_req)
            for _ in range(max_req + 20)
        ]
    )
    allowed = sum(1 for limited in results if limited is False)
    blocked = sum(1 for limited in results if limited is True)
    assert allowed == max_req
    assert blocked == 20


@pytest.mark.asyncio
async def test_redis_lua_allows_under_limit() -> None:
    backend = RedisRateLimitBackend(_AtomicFakeRedis())
    for i in range(3):
        limited = await backend.is_limited("k", window=60, max_requests=3)
        assert limited is False, f"request {i} should be allowed"
    assert await backend.is_limited("k", window=60, max_requests=3) is True


@pytest.mark.asyncio
async def test_real_redis_lua_script_loads(real_redis) -> None:
    """Load the production Lua via redis-py EVAL (syntax errors fail here)."""
    prefix = f"rl:test:{uuid.uuid4().hex}"
    key = f"{prefix}:load"
    script = real_redis.register_script(_RL_SLIDING_WINDOW_LUA)
    try:
        result = await script(
            keys=[key],
            args=[time.time(), 60, 5, f"m-{uuid.uuid4().hex}"],
        )
        assert int(result) == 0
    finally:
        await real_redis.delete(key)


@pytest.mark.asyncio
async def test_real_redis_lua_does_not_overshoot_under_concurrency(real_redis) -> None:
    backend = RedisRateLimitBackend(real_redis)
    suffix = uuid.uuid4().hex
    limit_key = f"real:{suffix}"
    redis_key = f"rl:hits:{limit_key}"
    max_req = 5
    try:
        results = await asyncio.gather(
            *[
                backend.is_limited(limit_key, window=60, max_requests=max_req)
                for _ in range(max_req + 20)
            ]
        )
        allowed = sum(1 for limited in results if limited is False)
        blocked = sum(1 for limited in results if limited is True)
        assert allowed == max_req
        assert blocked == 20
        stored = await real_redis.zcard(redis_key)
        assert int(stored) == max_req
    finally:
        await real_redis.delete(redis_key)


@pytest.mark.asyncio
async def test_abuse_warned_at_prunes_stale() -> None:
    from bot.config import get_settings
    from bot.middlewares.rate_limit import MemoryRateLimitBackend, RateLimitMiddleware

    mw = RateLimitMiddleware(backend=MemoryRateLimitBackend(max_tracked_users=100))
    window = get_settings().rate_limit_abuse_window_seconds
    now = time.monotonic()
    mw._abuse_warned_at[1] = now - window - 1.0
    mw._abuse_warned_at[2] = now
    await mw._maybe_abuse_warn(99, 0)
    assert 1 not in mw._abuse_warned_at
    assert 2 in mw._abuse_warned_at


@pytest.mark.asyncio
async def test_rate_limit_notice_uses_stored_russian(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from bot.locales.ru import TEXTS as RU_TEXTS
    from bot.middlewares.rate_limit import MemoryRateLimitBackend, RateLimitMiddleware

    monkeypatch.setattr(
        "bot.middlewares.rate_limit.load_stored_language",
        AsyncMock(return_value="ru"),
    )
    mw = RateLimitMiddleware(backend=MemoryRateLimitBackend(max_tracked_users=100))
    message = MagicMock()
    message.from_user = MagicMock(id=7, language_code="en")
    message.answer = AsyncMock()

    await mw._notify_limited(message, None, 30)

    message.answer.assert_awaited_with(RU_TEXTS.RATE_LIMITED.format(seconds=30))
