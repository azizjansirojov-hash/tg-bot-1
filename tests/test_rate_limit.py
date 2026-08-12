"""In-memory rate-limit backend tests."""

from __future__ import annotations

import pytest
from bot.middlewares.rate_limit import MemoryRateLimitBackend


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
