"""Health probe tests: liveness vs cached readiness."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest


class _CountingConn:
    def __init__(self, parent: _CountingEngine) -> None:
        self._parent = parent

    async def execute(self, *_args: object, **_kwargs: object) -> None:
        self._parent.calls += 1

    async def __aenter__(self) -> _CountingConn:
        return self

    async def __aexit__(self, *_args: object) -> None:
        return None


class _CountingEngine:
    def __init__(self) -> None:
        self.calls = 0

    def connect(self) -> _CountingConn:
        return _CountingConn(self)


@pytest.mark.asyncio
async def test_livez_does_not_touch_db(monkeypatch: pytest.MonkeyPatch) -> None:
    from bot import __main__ as main_mod

    engine = _CountingEngine()
    monkeypatch.setattr(main_mod, "get_engine", lambda: engine)
    request = MagicMock()
    resp = await main_mod.livez_handler(request)
    assert resp.status == 200
    assert engine.calls == 0


@pytest.mark.asyncio
async def test_healthz_caches_db_probe(monkeypatch: pytest.MonkeyPatch) -> None:
    from bot import __main__ as main_mod

    main_mod.reset_healthz_cache()
    engine = _CountingEngine()
    monkeypatch.setattr(main_mod, "get_engine", lambda: engine)
    request = MagicMock()
    first = await main_mod.healthz_handler(request)
    second = await main_mod.healthz_handler(request)
    assert first.status == 200
    assert second.status == 200
    assert engine.calls == 1
    main_mod.reset_healthz_cache()
