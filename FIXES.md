# Audit CRITICAL / MEDIUM fixes

Remediation of the seven issues listed in the implementation plan (no `AUDIT.md` was present in the repo). Final verification: `pytest` **41 passed, 4 skipped**; `ruff check bot tests` **All checks passed**; `pip-audit -r requirements.txt` **No known vulnerabilities found**.

Note: installed `pip-audit` 2.9.0 does **not** support `--severity-level` (the flag in `.github/workflows/ci.yml` is invalid for this version). The audit was run as `pip-audit -r requirements.txt --progress-spinner off`, which reports all severities.

---

## 1. CRITICAL — Vulnerable `aiohttp`

**Status:** Fixed.

**Change:** Pinned `aiohttp==3.14.3` (aiogram 3.30.0 allows `aiohttp>=3.9,<3.15`; 3.14.3 is the latest 3.14.x with no High/Critical advisories on Snyk). Regenerated the hashed lockfile with the command already documented in `requirements.txt`:

```text
uv pip compile --python-version 3.11 --generate-hashes -o requirements.txt requirements.in
```

**Files:**
- [`requirements.in`](requirements.in) — pin `aiohttp==3.14.3`
- [`requirements.txt`](requirements.txt) — regenerated hashes (`aiohttp==3.14.3`)
- [`tests/test_startup.py`](tests/test_startup.py) — version assertion; mocked polling start; webhook `TCPSite` bind + `GET /healthz`

**Verified:**
- `pip-audit -r requirements.txt` → no known vulnerabilities (including aiohttp)
- `pytest tests/test_startup.py` — 4 passed (polling + webhook smoke, no live Telegram)

**Trade-off:** none. Stayed on 3.14.x rather than 3.15+ to remain inside aiogram's constraint.

---

## 2. CRITICAL — Multi-replica silently weakens rate limits / FSM

**Status:** Fixed.

**Change:**
- Loud `WARNING` at startup when `BOT_MODE=webhook` and `USE_REDIS=false` (`_warn_if_webhook_without_redis` in [`bot/__main__.py`](bot/__main__.py) ~lines 42–56, called from `main()`).
- New env `BOT_REPLICA_COUNT` (default `1`). If `>1` and `USE_REDIS=false`, `Settings` raises `ValueError` (fail fast). Single-replica webhook without Redis remains allowed (warning only).

**Files:**
- [`bot/config.py`](bot/config.py) — `bot_replica_count` field; `validate_redis_config` (~lines 108–138)
- [`bot/__main__.py`](bot/__main__.py) — warning helper + call from `main()`
- [`tests/test_config.py`](tests/test_config.py) — replica count tests
- [`tests/test_startup.py`](tests/test_startup.py) — caplog warning test
- [`.env.example`](.env.example), [`README.md`](README.md), [`SECURITY_HARDENING_REPORT.md`](SECURITY_HARDENING_REPORT.md)

**Verified:** pytest config + startup warning tests.

**Trade-off:** webhook + no Redis is still legal for one process (common on Railway/Render). Operators must set `BOT_REPLICA_COUNT` for the fail-fast path; platforms do not expose a portable replica-count env we can trust.

---

## 3. CRITICAL — `docker-compose.yml` published ports / default credentials

**Status:** Fixed (documentation / comments only; no runtime change).

**Change:** Prominent LOCAL DEVELOPMENT ONLY block at the top of compose. README and `.env.example` already noted dev-only defaults; README security/deploy sections now state production must use unique credentials and must not run this compose file unmodified on a public host.

**Files:**
- [`docker-compose.yml`](docker-compose.yml) lines 1–13
- [`README.md`](README.md) deploy + security notes
- [`.env.example`](.env.example)

**Verified:** manual review of comments/docs.

---

## 4. MEDIUM — No global aiogram error handler

**Status:** Fixed.

**Change:** `unhandled_error_handler` registered on the dispatcher (`dp.errors.register`). Logs at **ERROR** with `user_id`, `update_id`, exception type, and full traceback (`exc_info=`). Then replies with `TEXTS.GENERIC_ERROR` (message or callback alert). Notify failures are logged separately and do not recurse.

**Files:**
- [`bot/__main__.py`](bot/__main__.py) — `unhandled_error_handler` (~122–152), register in `_build_dispatcher` (~196)
- [`tests/test_error_handler.py`](tests/test_error_handler.py)

**Verified:** pytest error-handler tests (message + callback).

---

## 5. MEDIUM — `WEBHOOK_URL` not required to be HTTPS

**Status:** Fixed.

**Change:** `validate_webhook_config` rejects URLs that do not start with `https://` (case-insensitive). Plain `http://` is rejected even for localhost (safer; use a TLS tunnel for local webhook tests).

**Files:**
- [`bot/config.py`](bot/config.py) ~lines 190–195
- [`tests/test_config.py`](tests/test_config.py) — `test_webhook_url_requires_https`, `test_webhook_url_https_ok`
- [`SECURITY_HARDENING_REPORT.md`](SECURITY_HARDENING_REPORT.md)

**Verified:** pytest config tests.

---

## 6. MEDIUM — Redis rate limiter check-then-act race

**Status:** Fixed.

**Change:** Replaced pipeline `zcard` + speculative `zadd` + undo with a Lua script (`EVAL` via `register_script`). Trim, `ZCARD`, and conditional `ZADD` run in one atomic round-trip. Unique members use `{now}:{uuid}` to avoid timestamp collisions. `record_block` remains a pipeline (telemetry only).

**Files:**
- [`bot/middlewares/rate_limit.py`](bot/middlewares/rate_limit.py) — `_RL_SLIDING_WINDOW_LUA` and `RedisRateLimitBackend.is_limited` (~123–168)
- [`tests/test_rate_limit.py`](tests/test_rate_limit.py) — concurrent `asyncio.gather` of `max+20` calls; allowed count equals `max_requests`

**Verified:** pytest Redis backend tests with an in-process fake that serializes `register_script` the same way Redis serializes Lua.

**Not done / explicit:** `fakeredis[lua]` was **not** added to `requirements-dev.txt`. Lua execution was verified against a lock-serialized fake that implements the same check-then-add semantics. A live Redis EVAL was not run in this environment.

---

## 7. MEDIUM — Unauthenticated `/healthz` hits the DB on every call

**Status:** Fixed.

**Approach chosen:** split endpoints **and** cache the DB probe (not throttle-only).

| Path | Role | Database |
|------|------|----------|
| `GET /livez` | Liveness | none |
| `GET /healthz` | Readiness (Dockerfile HEALTHCHECK unchanged) | `SELECT 1`, cached ~5s (`HEALTHZ_DB_CACHE_SECONDS`) with a lock to avoid stampedes |

**Why this instead of making `/healthz` liveness-only:** existing HEALTHCHECK and ops notes treat `/healthz` as "can talk to Postgres". Caching keeps that meaning while bounding load from a public probe.

**Files:**
- [`bot/__main__.py`](bot/__main__.py) — `livez_handler`, cached `healthz_handler`, `/livez` route (~68–119, ~230–231)
- [`tests/test_healthz.py`](tests/test_healthz.py)
- [`README.md`](README.md) deploy section

**Verified:** pytest — `/livez` never calls the engine; two `/healthz` calls within the TTL produce one `SELECT 1`.

---

## Final verification

| Check | Result |
|-------|--------|
| `pytest` | 41 passed, 4 skipped |
| `ruff check bot tests` | All checks passed |
| `pip-audit -r requirements.txt` | No known vulnerabilities found |
