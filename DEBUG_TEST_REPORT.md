# DEBUG TEST REPORT — End-to-End Verification Pass

**Date:** 2026-08-12  
**Session:** `0bbaee`  
**Runtime log:** `debug-0bbaee.log`  
**Harness:** `scripts/verify_debug_runtime.py` (+ temporary NDJSON instrumentation in `bot/db/base.py`, `bot/services/telegram.py`)  
**Compared against:** `FIX_REPORT.md` / `GITHUB_PUSH_REPORT.md` / `SECURITY_HARDENING_REPORT.md` (restored from `HEAD` during this pass after they were missing from the working tree)

---

## Environment

| Item | This session |
|------|----------------|
| Host Python | **3.14.7** only (`py -0p` shows 3.14; **no Python 3.11** installed) |
| Dockerfile Python | **3.11-slim** (`FROM python:3.11-slim`) — **differs from host** |
| Docker CLI | Present: Docker `29.6.2`, Compose `v5.3.1` |
| Docker daemon | **Not available** — `docker info` shows Client only; Docker Desktop executable **not found** at default Program Files / LocalAppData paths; cannot build/run images or `docker compose up` |
| Postgres (`localhost:5432`) | **Unreachable** (`TimeoutError` / Alembic `ConnectionRefusedError`) |
| Redis (`localhost:6379`) | **Unreachable** |
| `.env` | Present. Required keys: `BOT_TOKEN`, `DATABASE_URL`, `STORAGE_CHANNEL_ID`, `ADMIN_IDS` → **PRESENT_NONEMPTY**. Also present: `BOT_MODE`, `WEBHOOK_*`. `USE_REDIS` / `REDIS_URL` / `TEST_DATABASE_URL` → **ABSENT** |
| Live Telegram E2E | **Not performed** — no disposable live walkthrough in this pass; functional claims below are **simulated** via pytest + harness unless noted |

**Honest limitation:** Any claim that requires a real Postgres, Redis, Docker image build, container HEALTHCHECK, or live BotFather token interaction is **not verified here**. Code-path simulation does **not** substitute for those.

---

## Results table

| Step | What was tested | Result | Notes / output |
|------|-----------------|--------|----------------|
| 0 | Host Python vs Dockerfile 3.11 | **Fail** (env mismatch) | Host `Python 3.14.7`; image/CI target 3.11. No local 3.11 interpreter. |
| 1 | Docker availability (CLI + daemon) | **Fail** (daemon) | CLI/Compose OK; daemon/Desktop missing → image build, compose, HEALTHCHECK inspect **blocked**. |
| 2 | `.env` required keys present (no secret values printed) | **Pass** | `BOT_TOKEN`, `DATABASE_URL`, `STORAGE_CHANNEL_ID`, `ADMIN_IDS` all PRESENT_NONEMPTY. |
| 3 | PostgreSQL reachable | **Fail** | TCP `127.0.0.1:5432` closed; DB-dependent work skipped. |
| 4 | Hash-locked `pip install --require-hashes -r requirements.txt` | **Pass*** | Succeeded on **Python 3.14** (exit 0, packages already satisfied; no hash mismatch errors). *Not* verified inside `python:3.11-slim` image — **still first-time-unverified against real Docker runtime** (same gap FIX_REPORT item 4 called out). |
| 5 | `pytest -v` full suite | **Pass** (partial) | **27 passed, 4 skipped**, 0 failed. Skips: all `tests/test_crud_upsert.py` (`TEST_DATABASE_URL not set`). |
| 6 | `ruff check` | **Fail** | Pre-existing / tooling noise: `alembic/env.py` I001; plus **debug instrumentation** E501/I001 in `bot/services/telegram.py` / `bot/db/base.py`; harness `scripts/verify_debug_runtime.py` E501/F401. **Do not ship with instrumentation.** |
| 7 | `mypy bot` (advisory) | **Fail** (advisory) | 1 error: `bot/handlers/user.py:61` — `Bot \| None` passed to `safe_send_video` expecting `Bot`. Matches FIX_REPORT “mypy advisory” posture; not a CI blocker by design. |
| 8 | CRUD concurrent upsert vs real DB (`TEST_DATABASE_URL`) | **Skipped** | Gap in FIX_REPORT §7 **still open**. No Postgres → race-safety test never ran. |
| 9 | `alembic upgrade head` clean DB | **Fail** | Connection refused to configured Postgres. No schema applied. |
| 10 | `alembic downgrade -1` then `upgrade head` | **Skipped** | Blocked by step 9. |
| 11 | Live schema vs `bot/db/models.py` (`movies.code` unique, `users.telegram_id` PK) | **Skipped** (runtime) | Migration **source** review: `001_initial_movies_users.py` creates unique index `ix_movies_code` and PK on `users.telegram_id` — **matches models**, but **not inspected on a live DB**. |
| 12 | Bot boot polling (`BOT_MODE=polling`) | **Fail** / incomplete | Log: `Booting bot mode=polling use_redis=False storage_channel_configured=True admin_count=1` then process could not complete healthy long-run without DB (Postgres down). |
| 13 | Clean SIGTERM / Ctrl+C shutdown (no traceback) | **Skipped** | No clean completed polling session against reachable DB. |
| 14 | Webhook mode boot + `/healthz` → 200 when DB up | **Skipped** | No DB; webhook HTTP listener not verified. |
| 15 | `/healthz` non-200 when DB unreachable | **Skipped** | Cannot contrast healthy vs unhealthy DB state without controllable Postgres. |
| 16 | Dockerfile HEALTHCHECK under `BOT_MODE=polling` (`docker inspect` Health.Status) | **Skipped** | Docker daemon unavailable. Code review only: HEALTHCHECK exits 0 when `BOT_MODE != webhook`. |
| 17 | Dockerfile HEALTHCHECK under `BOT_MODE=webhook` | **Skipped** | Same — not built/run. |
| 18 | User valid code → video + plain caption (item 1) | **Pass** (simulated) | Harness log: `verify:caption` `parse_mode: null`, `ok: true`. Not live-Telegram. |
| 19 | User invalid / missing code → graceful not-found | **Pass** (simulated / unit-adjacent) | Covered indirectly by handler design + suite; **not** live Telegram. No crash observed in harness paths exercised. |
| 20 | Malicious title HTML regression (admin HTML escape + plain caption) | **Pass** (simulated) | Log: `escape_html` ok; `list_escape` / `success_escape` ok; caption `parse_mode=None`. **Not** live-Telegram-verified. |
| 21 | Title >255 rejected; stay in `waiting_for_title` (item 3) | **Pass** (simulated + pytest) | `test_title_too_long_stays_in_waiting_for_title` PASSED; harness `verify:title_len` ok. |
| 22 | Overwrite uses FSM code, not callback payload (item 10) | **Pass** (simulated + pytest) | `test_overwrite_callback_uses_fsm_code_not_payload` PASSED; harness `verify:overwrite_fsm` ok (`message_has_555`). Keyboards use `overwrite:yes\|no` / `save:yes\|no`. |
| 23 | Admin CRUD (`/list_codes`, `/delete_code`, `/stats`, `/auditlog`) + non-admin denial | **Skipped** (live) / partial unit | No live Telegram admin session. List/success HTML escaping helpers verified in harness only. |
| 24 | Rate limit block + admin exemption on numeric code layer | **Pass** (simulated) | Harness: `blocked_non_admin: 2`, `blocked_admin: 0`, `ok: true`. Memory backend only. |
| 25 | Redis path: compose Redis + `USE_REDIS=true` rate-limit/FSM subset | **Skipped** | Redis TCP closed; Docker compose cannot start Redis here. FIX_REPORT §7 Redis CI gap **still open**. |
| 26 | Redis rate-limit key TTL (`redis-cli TTL`) | **Skipped** | No Redis. |
| 27 | FSM survives restart with Redis; lost with MemoryStorage | **Skipped** | No Redis / no controlled restart E2E. Documented limitation remains **theoretical** here. |
| 28 | Flood-wait: DB session released before `TelegramRetryAfter` sleep (item 9) | **Pass** (simulated) | Log order: `release_session` → `send_start` → `TelegramRetryAfter before sleep` → `sleep:0`. Events: `["release_before","commit","close","release_after","send_start","sleep:0"]`. |

---

## Hypotheses exercised (debug session)

Used to structure instrumentation / harness (not a single production incident):

| ID | Hypothesis | Verdict | Evidence |
|----|------------|---------|----------|
| A | HTML-dangerous titles are escaped in admin HTML helpers | **CONFIRMED** (simulated) | `debug-0bbaee.log` `verify:html`, `verify:list_escape`, `verify:success_escape` all `ok: true` |
| B | Video captions force `parse_mode=None` | **CONFIRMED** (simulated) | `verify:caption` `parse_mode: null` |
| C | Overlong titles rejected without leaving `waiting_for_title` | **CONFIRMED** | pytest + `verify:title_len` / `verify:title_ok` |
| D | Overwrite confirmation uses FSM-stored code | **CONFIRMED** | pytest + `verify:overwrite_fsm` |
| E | Session released before flood-wait sleep | **CONFIRMED** (simulated) | `release_session` then sleep in log order |
| F | Admins exempt from code-layer rate limit | **CONFIRMED** (simulated) | `verify:rate_limit` |

---

## Regressions found (vs FIX_REPORT claims)

1. **Docker / Python 3.11 lockfile verification still not done** — FIX_REPORT item 4 claimed compile for 3.11 but noted Docker unavailable on the build host. **This host still cannot run the image.** Hash install on 3.14 succeeded, which is **necessary but not sufficient** for the Docker claim.
2. **CRUD race-safety still unverified locally** — same §7 gap; 4 tests still skip without `TEST_DATABASE_URL`.
3. **Redis multi-replica / TTL / FSM restart claims** — still **untested end-to-end** (explicit FIX_REPORT gap).
4. **Bot cannot complete a real boot smoke** without Postgres — polling starts logging then cannot be called “healthy deploy-ready” here.
5. **Working-tree hygiene:** `FIX_REPORT.md`, `GITHUB_PUSH_REPORT.md`, `SECURITY_HARDENING_REPORT.md` were **deleted** in the working tree at session start (`git status` showed `D`); restored from `HEAD` during this pass. Investigate how they were removed before tagging a release.
6. **Temporary debug instrumentation remains in tree** (`bot/db/base.py`, `bot/services/telegram.py`, `scripts/verify_debug_runtime.py`, `debug-0bbaee.log`) — **must be removed before production deploy**; current ruff failures partly come from that instrumentation.
7. **Ruff is not clean** on `alembic/env.py` (I001) even aside from debug logs — CI ruff job would fail if it checks the whole tree with the same config.

No evidence in this session that item 1 (plain captions + escape), item 3 (title length), item 9 (session release), item 10 (FSM overwrite), or admin code-limit exemption are **broken** in simulated tests — those paths **held up** under harness/pytest.

---

## Gaps unverifiable in this environment (manual before production)

Operator must do these on a machine with Docker Desktop (or Linux Docker daemon) + Postgres + Redis + a **disposable** BotFather token:

1. `docker build` and confirm `pip install --require-hashes` inside the **3.11** image (close item 4 for real).
2. `docker compose up -d db redis`; set `TEST_DATABASE_URL`; re-run `tests/test_crud_upsert.py` including concurrent upserts.
3. `alembic upgrade head` / `downgrade -1` / `upgrade head`; `\d movies` / `\d users` / `\d admin_audit_log`.
4. Boot polling + webhook; prove `/healthz` 200 vs DB-down; `docker inspect` Health.Status for both `BOT_MODE` values.
5. Live Telegram: `/start`, valid code, invalid code, malicious title add+lookup, title>255, overwrite FSM, admin CRUD, non-admin denial, rate-limit + admin exemption.
6. `USE_REDIS=true`: rate-limit TTL via `redis-cli TTL`, FSM survival across process restart vs MemoryStorage loss.
7. Remove debug instrumentation and re-run `ruff` / pytest clean.

**Do not use or expose the production bot token for this smoke.** Rotate if it was shared in any prior agent session (see `GITHUB_PUSH_REPORT.md` follow-up).

---

## Go / No-Go

### **No-Go for production deploy as-is.**

**Why (blocking):**

- Postgres unreachable → migrations, real upserts, healthchecks, and real bot boot were not proven.
- Docker daemon unavailable → image hash install on 3.11, compose Redis/DB, and HEALTHCHECK behavior unproven.
- Live Telegram functional walkthrough not done.
- Debug instrumentation still present; ruff unclean.
- FIX_REPORT’s own remaining gaps (CRUD concurrency, Redis E2E) remain open on this host.

**What is reasonably trusted from this pass:** unit/simulated coverage for HTML/caption, title length, FSM overwrite, memory rate-limit admin exemption, and session-release-before-flood-sleep — **27/31 tests green** with the 4 DB tests skipped by design when `TEST_DATABASE_URL` is unset.

**Minimum to flip toward Go:** Docker+Postgres+Redis smoke (steps 8–17, 25–27), live disposable-bot walkthrough (18–24), strip debug logs, clean ruff, and optionally fix the advisory mypy `Bot | None` call site.

---

## Commands / artifacts captured this session

```text
python --version          → Python 3.14.7
docker --version          → 29.6.2 (daemon unavailable)
pytest -v                 → 27 passed, 4 skipped
pip install --require-hashes -r requirements.txt  → exit 0 on 3.14
alembic upgrade head      → ConnectionRefusedError (Postgres down)
mypy bot                  → 1 error (user.py:61)
scripts/verify_debug_runtime.py → all harness ok flags true (see debug-0bbaee.log)
```
