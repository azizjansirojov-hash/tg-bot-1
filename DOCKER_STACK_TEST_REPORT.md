# DOCKER STACK TEST REPORT — Real Container Verification Pass

**Date:** 2026-08-12  
**Compared against:** `DEBUG_TEST_REPORT.md` (Gaps unverifiable), `FIX_REPORT.md`, `CLEANUP_REPORT.md`  
**Constraint (locked):** No disposable BotFather token; **no live Telegram API calls** this session — by explicit decision, not by unavailability.

---

## Environment

| Item | This session |
|------|----------------|
| Docker daemon | **Live** — `Server Version: 29.6.2`, OS `Docker Desktop` / WSL2, Context `desktop-linux` |
| Docker CLI | `29.6.2` |
| Compose | `Docker Compose version v5.3.1` (v2-compatible plugin) |
| Host Python (pytest/alembic) | `3.14.7` |
| Image runtime | `Python 3.11.15` (`python:3.11-slim` via `tg-bot-1:debug`) |
| Compose services | `postgres:16-alpine` + `redis:7-alpine` — both **healthy** during verification |
| `.env` | Present locally; session used process env overrides for `DATABASE_URL` / `TEST_DATABASE_URL` / Redis — **not written into tracked files** |
| Live Telegram | **No live Telegram API calls made this session — by explicit decision, not by unavailability.** |

---

## Results table

| Step | What was tested | Result | Real output / evidence |
|------|-----------------|--------|------------------------|
| 0 | Docker daemon usable (`docker info` Server section) | **Pass** | `Server Version: 29.6.2`; Containers/Images listed; not Client-only |
| 0b | Compose v2 available | **Pass** | `Docker Compose version v5.3.1` |
| 1 | `docker build -t tg-bot-1:debug .` | **Pass** | Build exit 0; stage `#15 RUN pip install --no-cache-dir --require-hashes --prefix=/install -r requirements.txt` → `Successfully installed aiogram-3.30.0 …` — **zero hash-mismatch / wheel-resolution errors** |
| 1b | Image Python version | **Pass** | `docker run --rm tg-bot-1:debug python --version` → `Python 3.11.15` |
| 2 | `docker compose up -d db redis` healthy | **Pass** | `tg-bot-1-db-1` Up (healthy) `:5432`; `tg-bot-1-redis-1` Up (healthy) `:6379` |
| 2b | Session `TEST_DATABASE_URL` → compose Postgres | **Pass** | `postgresql+asyncpg://postgres:postgres@localhost:5432/tgbot` (process env only) |
| 3 | `alembic upgrade head` | **Pass** | `Context impl PostgresqlImpl` / transactional DDL; DB already at head from volume, then re-verified via downgrade/upgrade |
| 3b | `alembic downgrade -1` then `upgrade head` | **Pass** | Downgrade `002_admin_audit → 001_initial`; upgrade `001_initial → 002_admin_audit` |
| 3c | Live `\d movies` / `\d users` / `\d admin_audit_log` | **Pass** | `ix_movies_code UNIQUE, btree (code)`; `users_pkey PRIMARY KEY, btree (telegram_id)`; `admin_audit_log` present with indexes |
| 4 | `pytest -v tests/test_crud_upsert.py` | **Fail** (partial) | **2 failed, 2 passed.** Concurrent + window count **PASSED**. Overwrite + user increment **FAILED** (see NEW issues) |
| 4b | Full `pytest -v` | **Fail** (partial) | **29 passed, 2 failed, 0 skipped** (not 31/0 — same two upsert failures). Previously-skipped DB tests **did execute** |
| 4c | `ruff check .` | **Pass** | `All checks passed!` (instrumentation already removed per `CLEANUP_REPORT.md` / `af3e707`) |
| 5a | Full polling boot + clean SIGTERM vs Telegram | **Skipped** | Would call `api.telegram.org` (`delete_webhook` / polling). Explicit no-Telegram decision |
| 5b | Full webhook boot via `python -m bot` | **Skipped** | Architectural: `run_webhook` calls `set_webhook` **before** HTTP/`/healthz` starts (`bot/__main__.py`) |
| 5c | `/healthz` → 200 with DB up (real `healthz_handler`) | **Pass** | Ephemeral aiohttp importing `bot.__main__.healthz_handler`: `STATUS=200 BODY={"status": "ok"}` |
| 5d | `/healthz` non-200 when DB stopped | **Pass** | `docker compose stop db` → `STATUS=503`; logs `Health check failed` + connection error; `start db` → `STATUS=200` again |
| 5e | Docker HEALTHCHECK `BOT_MODE=polling` | **Pass** | Container CMD overridden to `sleep infinity` (no bot/Telegram). `State.Health.Status=healthy`, ExitCode 0 on probes — does **not** falsely report unhealthy |
| 5f | Docker HEALTHCHECK `BOT_MODE=webhook` | **Pass** | Override CMD ran real `healthz_handler` on `:8080` on compose network; `Status=healthy`, ExitCode 0 |
| 6a | `RedisRateLimitBackend` threshold blocking | **Pass** | Hits 1–5 `limited=False`, 6–7 `limited=True` (`RATE_LIMIT_MAX_REQUESTS=5`) |
| 6b | Rate-limit key TTL via `redis-cli TTL` | **Pass** | Script: `ttl=61` for `rl:hits:…` with `window+1=61`; separate probe: `redis-cli TTL` → `60`, `TYPE` → `zset` |
| 6c | `RedisStorage` FSM survives fresh-instance “restart” | **Pass** | Wrote `AdminAddMovie:waiting_for_title` + `{'code':'4242'}`; keys `fsm:555001:555001:state|data`; new `RedisStorage` read same state/data |
| 6d | `MemoryStorage` state lost on new instance | **Pass** | Fresh `MemoryStorage`: `state=None data={}` |
| 7 | Live Telegram functional walkthrough | **Skipped** | Explicit decision — no disposable token. Not re-simulated; see `DEBUG_TEST_REPORT.md` simulated rows 18–24 for prior harness-only evidence |

---

## Gaps closed (from `DEBUG_TEST_REPORT.md` “Gaps unverifiable”)

| # | Gap | Status after this pass |
|---|-----|------------------------|
| 1 | `docker build` + hash-locked pip inside **3.11** image | **Closed** — real build + `Python 3.11.15` |
| 2 | Compose `db`/`redis` + `TEST_DATABASE_URL` + upsert tests | **Partially closed** — stack up; tests **ran** (no longer skipped). Concurrent upsert **Pass**; overwrite/increment assertions **Fail** (NEW issue) |
| 3 | Alembic upgrade/downgrade + live `\d` | **Closed** — both directions + unique/PK confirmed live |
| 4 | Boot polling/webhook; `/healthz` 200 vs DB-down; `docker inspect` Health | **Partially closed** — `/healthz` + HEALTHCHECK **Pass** without Telegram. Full `python -m bot` boot/SIGTERM **still Skipped by choice** (and blocked by Telegram-before-listen architecture) |
| 5 | Live Telegram walkthrough | **Still open — accepted deliberate gap** |
| 6 | Redis TTL + FSM survival vs MemoryStorage | **Closed** — real Redis backends + `redis-cli` evidence |
| 7 | Remove debug instrumentation; clean ruff | **Already closed** before this pass (`CLEANUP_REPORT.md`); reconfirmed `ruff check .` Pass |

---

## NEW issues found (only visible with real Docker/Postgres/Redis)

### 1. Upsert return values stale in same session (`expire_on_commit=False`) — **Fail**

Against live Postgres, with the test fixture (and production `async_sessionmaker(..., expire_on_commit=False)`):

| Test | Result |
|------|--------|
| `test_concurrent_movie_upserts` | **PASSED** — race-safe insert does not raise; count=1 |
| `test_list_movies_window_count` | **PASSED** |
| `test_upsert_movie_insert_and_overwrite` | **FAILED** — returned `m2.title == 'One'` after overwrite to `'Two'` |
| `test_upsert_user_activity_increments` | **FAILED** — returned `request_count == 1` after second upsert |

**Follow-up probe:** the **database row is correct** (`SELECT` shows title `Two` / `request_count=2`); a **fresh session** loads the updated values. The ORM instance returned from `.returning(Movie|User)` is merged into the identity map and **not populated from RETURNING** when the entity was already present.

**Production impact (honest):** Admin save confirmation uses FSM title, not the returned Movie, so user-facing overwrite confirmations are likely fine. Any code that trusts the returned object’s attributes after a second upsert in the **same** session (or after prior load of the same PK) can show stale data. Fix direction (not applied this session): `execution_options(populate_existing=True)` on the insert, or `session.refresh` / expire before return.

### 2. Webhook HTTP server unreachable without Telegram handshake — architectural

`main()` → `run_webhook()` → `bot.set_webhook(...)` **before** `TCPSite.start()`. Deploy platforms that health-check `/healthz` during cold start may race Telegram API latency/failure. Documented; not fixed in this pass.

### 3. Host Python still 3.14 vs image 3.11

Pytest/alembic ran on host 3.14 against real Postgres; image lockfile verified on 3.11. No hash failure observed. Residual risk: host-only quirks (e.g. asyncio deprecation warnings) do not equal CI/image behavior.

---

## Updated Go / No-Go

### Verdict: **Conditional Go for infra push — No-Go for claiming full production smoke complete**

Supersedes `DEBUG_TEST_REPORT.md` blanket **No-Go** driven by missing Docker/Postgres/Redis.

**Now proven with real containers:**

- 3.11 image builds with `--require-hashes`
- Compose Postgres + Redis healthy
- Migrations reversible; unique `movies.code` + PK `users.telegram_id` live
- Concurrent upsert race-safety under real Postgres
- `/healthz` reflects real DB connectivity (200 / 503)
- Dockerfile HEALTHCHECK correct for polling (always-ok path) and webhook (probes `/healthz`)
- Redis rate-limit TTL + FSM restart survival vs MemoryStorage loss

**Still blocking a confident “fully smoke-tested deploy” claim:**

1. **Telegram-live boot and functional walkthrough remain the one category never proven end-to-end across all sessions so far — accepted, deliberate gap for now**, not an oversight.
2. **Upsert ORM return staleness** failed two integration tests; DB writes are correct, but the API contract of returned entities is wrong under `expire_on_commit=False`. Treat as a **real defect** to fix before relying on returned objects (or fix the tests + production return path with `populate_existing`).

**Practical recommendation:** Safe to push **infra/image/CI-oriented** changes and to trust Docker/Redis/Postgres paths exercised here. Do **not** treat live Telegram behavior or same-session upsert return values as verified. Prefer fixing the upsert populate/expire issue before the next release tag if any handler path consumes returned Movie/User fields after conflict updates.

---

## Cleanup performed

| Action | Status |
|--------|--------|
| `docker rm -f tg-bot-hc-polling tg-bot-hc-webhook` | Done during session |
| `docker compose down` | Done at end of session |
| Remove `tg-bot-1:debug` image | Done at end of session |
| Delete ephemeral `_debug_healthz_server.py`, `_debug_redis_verify.py` | Done at end of session |
| No `TEST_DATABASE_URL` / test tokens written to tracked files | Confirmed — process env only |
| No `api.telegram.org` calls | Confirmed by session constraint |

---

## Commands / artifacts captured

```text
docker info                     → Server Version: 29.6.2
docker compose version          → v5.3.1
docker build -t tg-bot-1:debug . → exit 0; require-hashes OK
docker run --rm tg-bot-1:debug python --version → Python 3.11.15
docker compose up -d db redis   → both healthy
alembic downgrade -1 / upgrade head → OK
psql \d movies                  → ix_movies_code UNIQUE
pytest -v                       → 29 passed, 2 failed, 0 skipped
ruff check .                    → All checks passed
GET /healthz (DB up/down)       → 200 / 503 / 200
docker inspect Health           → polling healthy; webhook healthy
RedisRateLimitBackend + TTL     → block at 5; TTL≈60–61
RedisStorage vs MemoryStorage   → survive / lost as documented
```
