# FIX REPORT — Full Audit Remediation

**Date:** 2026-08-12  
**Scope:** Items 1–19 from `PROJECT_AUDIT.md` / remediation plan

---

## 1. Summary

This pass hardens the Telegram movie-code bot for production: HTML escaping and plain-text video captions, title length validation, race-safe PostgreSQL upserts, early DB session release before Telegram flood-wait sleeps, FSM-authoritative overwrite/save callbacks, bounded in-memory rate limits plus optional Redis-backed FSM/rate-limiting (`USE_REDIS`), Python 3.11-targeted hash-locked dependencies (via `uv pip compile --python-version 3.11`), expanded CI (pytest / ruff / advisory mypy / pip-audit), broader unit tests, Dockerfile healthcheck aware of `BOT_MODE`, and documentation (`SECURITY_HARDENING_REPORT.md`, README env/backup/admin gaps). No Alembic schema migrations were required.

---

## 2. Fixes Applied

| ID | Title | Files Changed | Status |
|----|-------|---------------|--------|
| 1 | HTML injection / plain captions | `bot/utils/html.py`, `bot/handlers/admin.py`, `bot/handlers/user.py`, `bot/services/telegram.py`, `bot/utils/__init__.py` | **Done** — captions use `parse_mode=None`; HTML messages escape dynamic titles/codes |
| 2 | Security hardening docs | `SECURITY_HARDENING_REPORT.md`, `README.md`, `bot/middlewares/rate_limit.py` (reference kept) | **Done** |
| 3 | Title length validation | `bot/constants.py`, `bot/handlers/admin.py`, `bot/locales/uz.py` | **Done** — reject >255, stay in `waiting_for_title` |
| 4 | Python 3.11 lockfile | `requirements.in`, `requirements.txt`, `requirements-dev.txt` | **Done** — compiled with `uv pip compile --python-version 3.11 --generate-hashes` (Docker unavailable on build host) |
| 5 | CI jobs | `.github/workflows/ci.yml` (replaced `security-audit.yml`), `pyproject.toml` | **Done** — pytest (+ Postgres service), ruff, advisory mypy, pip-audit; all on Python 3.11 |
| 6 | Redis-swappable FSM + rate limits | `bot/config.py`, `bot/__main__.py`, `bot/middlewares/rate_limit.py`, `docker-compose.yml`, `.env.example`, README, SECURITY doc | **Done** — `USE_REDIS=false` default; Redis service in compose |
| 7 | Race-safe upserts | `bot/db/crud.py`, `tests/test_crud_upsert.py` | **Done** — `INSERT … ON CONFLICT`; integration tests when `TEST_DATABASE_URL` set |
| 8 | Bound rate-limit memory | `bot/middlewares/rate_limit.py`, `bot/config.py` (`RATE_LIMIT_MAX_TRACKED_USERS`) | **Done** — eviction + cap; Redis keys use TTL |
| 9 | Don’t hold DB session across flood sleep | `bot/db/base.py` (`release_session`), `bot/middlewares/db.py`, `bot/handlers/user.py` | **Done** |
| 10 | FSM-stored code for overwrite/save | `bot/keyboards/inline.py`, `bot/handlers/admin.py` | **Done** — callbacks are `overwrite:yes\|no`, `save:yes\|no` |
| 11 | Expand tests | `tests/test_*.py`, `tests/conftest.py`, `pyproject.toml` | **Done** |
| 12 | README documentation gaps | `README.md` | **Done** |
| 13 | Dockerfile HEALTHCHECK for polling | `Dockerfile`, README | **Done** — webhook probes `/healthz`; polling exits 0 |
| 14 | Deduplicate pagination | `bot/keyboards/inline.py`, `bot/handlers/admin.py` | **Done** |
| 15 | Remove unused `get_session()` | `bot/db/base.py` | **Done** — replaced by `release_session` |
| 16 | Audit log retention | `SECURITY_HARDENING_REPORT.md`, `scripts/cleanup_audit_log.sql`, README | **Done** — documented manual SQL (no in-process cron) |
| 17 | Compose local-only credentials warning | `docker-compose.yml`, `README.md`, `.env.example` | **Done** |
| 18 | `/cancel` + `/auditlog` in admin table | `README.md` | **Done** |
| 19 | Paginated list count optimization | `bot/db/crud.py` | **Done** — `COUNT(*) OVER()` window; fallback count on empty page |

---

## 3. New Migrations

**No new Alembic revisions.** Upserts rely on existing unique `movies.code` and PK `users.telegram_id`. Audit retention is operational SQL only.

---

## 4. New/Changed Env Vars

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `USE_REDIS` | no | `false` | Enable Redis FSM + rate-limit backend |
| `REDIS_URL` | when `USE_REDIS=true` | `redis://localhost:6379/0` | Shared Redis URL |
| `RATE_LIMIT_MAX_TRACKED_USERS` | no | `10000` | In-memory rate-limit map cap (ignored if Redis) |

---

## 5. New Tests Added

| File | Coverage |
|------|----------|
| `tests/test_html_escape.py` | `escape_html` behavior |
| `tests/test_config.py` | DB URL scheme, webhook secret rules, Redis validation, admin IDs |
| `tests/test_rate_limit.py` | Sliding window, separate keys, eviction cap, block counts |
| `tests/test_admin_fsm.py` | Title too long / OK, overwrite uses FSM code, save cancel |
| `tests/test_title_validation.py` | `TITLE_MAX_LEN` matches ORM column |
| `tests/test_crud_upsert.py` | Upsert/overwrite/increment/concurrent/window count (**skipped** without `TEST_DATABASE_URL`) |
| `tests/conftest.py` | Env defaults + `get_settings` cache clear |
| Existing `tests/test_extract_storage_forward.py` | Still present |

Local run (no Postgres): **27 passed**.

---

## 6. Breaking Changes / Manual Steps Required

1. **Rebuild / reinstall dependencies** from the new hash-locked `requirements.txt` (includes `redis`). Prefer Python **3.11** (matches Dockerfile/CI).
2. **No Alembic upgrade** required for this change set.
3. **Multi-replica:** provision Redis; set `USE_REDIS=true` and `REDIS_URL`; read `SECURITY_HARDENING_REPORT.md`.
4. **Callback payloads changed** for overwrite/save (`overwrite:yes` / `save:no` without embedded code). In-flight admin FSM messages with old button payloads will show “invalid action” — admins should `/cancel` and restart the flow after deploy.
5. **Compose** now depends on a `redis` service healthcheck even when unused; `docker compose up` starts Redis alongside Postgres.
6. **CI workflow file renamed** to `.github/workflows/ci.yml` (old `security-audit.yml` removed).
7. **Production backups** remain operator-owned (managed Postgres / `pg_dump`); see README.

---

## 7. Known Remaining Gaps

| Gap | Why |
|-----|-----|
| CRUD concurrent tests need live Postgres (`TEST_DATABASE_URL`) | Unit environment had no local Postgres/Docker daemon during remediation; CI job provides Postgres service |
| Mypy is advisory (`continue-on-error: true`) | Codebase not fully typed; job runs and reports without failing the pipeline |
| Redis rate-limit / FSM not integration-tested in CI | No Redis service in CI yet; memory backend and unit paths are covered |
| In-process audit-log cleanup job not implemented | Intentionally documented as manual SQL only (item 16) |
| Single webhook registrar still required with multiple replicas | Platform concern; documented in hardening report, not automated |
| Captions remain plain text only | Intentional security decision — no HTML in user-facing video captions |

---

## Caption / HTML decision (item 1)

**Video captions use plain text** (`parse_mode=None` in `safe_send_video`), overriding the bot’s default HTML parse mode. Movie titles do not need markup for end users, and this avoids caption-side HTML injection entirely. Admin HTML messages still use `parse_mode="HTML"` with `escape_html()` on every dynamic interpolation.
