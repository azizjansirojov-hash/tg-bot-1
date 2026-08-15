# Security Hardening Report — Telegram Movie-Code Bot

This document describes the security and scaling posture of the bot after the
remediation pass. Operators must read the **Horizontal scaling** section before
running more than one replica.

## Threat model (summary)

- Secrets (bot token, DB URL, webhook secret) come from environment variables only.
- Admin actions are gated by `ADMIN_IDS`.
- Movie videos are never stored on disk; only Telegram `file_id` values are kept.
- User-facing errors are generic; stack traces stay in logs.

## Webhook security

When `BOT_MODE=webhook`:

- `WEBHOOK_URL` and `WEBHOOK_SECRET` are required.
- `WEBHOOK_SECRET` must be at least 32 characters and must not match a known
  weak/default value (see `bot/config.py`).
- aiogram `SimpleRequestHandler` validates the
  `X-Telegram-Bot-Api-Secret-Token` header before processing updates.

## Rate limiting

Two layers (see `bot/middlewares/rate_limit.py`):

1. **Global ceiling** — all update types, including admins
   (`RATE_LIMIT_GLOBAL_MAX_REQUESTS` / `RATE_LIMIT_GLOBAL_WINDOW_SECONDS`).
2. **Code-lookup limit** — digit-only movie codes; **admins exempt** so FSM
   numeric entry is not blocked (`RATE_LIMIT_MAX_REQUESTS` /
   `RATE_LIMIT_WINDOW_SECONDS`).

Abuse signal: after `RATE_LIMIT_ABUSE_THRESHOLD` blocks within
`RATE_LIMIT_ABUSE_WINDOW_SECONDS`, a WARNING is logged with `user_id` and
`block_count` only (no message text).

### In-memory backend (`USE_REDIS=false`, default)

- State lives in process memory.
- Idle keys are trimmed; tracked users are capped via
  `RATE_LIMIT_MAX_TRACKED_USERS` (default 10000).
- **Not safe for multi-replica deployments** — each replica has its own counters.

### Redis backend (`USE_REDIS=true`)

- Sliding windows use Redis sorted sets with **TTL/EXPIRE** on every key
  (window + 1 second), so keys do not grow without bound.
- Shared across replicas when all instances use the same `REDIS_URL`.

## FSM storage

| Mode | Storage | Multi-replica safe? |
|------|---------|---------------------|
| `USE_REDIS=false` | aiogram `MemoryStorage` | **No** — mid-flow state is lost on restart and not shared |
| `USE_REDIS=true` | aiogram `RedisStorage` | **Yes** — when all replicas share Redis |

## HTML / captions

- Dynamic titles and codes inserted into `parse_mode=HTML` admin messages are
  escaped via `bot.utils.html.escape_html`.
- Video captions are **plain text** (`parse_mode=None`) so titles never pass
  through HTML parsing.

## Database

- All queries use SQLAlchemy ORM / parameterized statements.
- Movie and user upserts use PostgreSQL `INSERT … ON CONFLICT` to avoid
  read-then-write races.
- Connection pool size is configurable (`DB_POOL_*`).
- DB sessions are released before Telegram flood-wait sleeps on the hot video
  delivery path so pool slots are not held during `asyncio.sleep`.

## Admin audit log retention

The `admin_audit_log` table grows with every add/overwrite/delete. This repo
does **not** run an automatic cleanup job. Example manual retention (90 days):

```sql
DELETE FROM admin_audit_log
WHERE timestamp < NOW() - INTERVAL '90 days';
```

Schedule via your host’s cron, a managed job, or a DBA runbook. See also
`scripts/cleanup_audit_log.sql`.

## Horizontal scaling checklist

Before running **more than one** bot process/replica:

1. Provision Redis and set `USE_REDIS=true` and `REDIS_URL`.
2. Ensure only **one** process registers the webhook, or use a single active
   webhook consumer pattern appropriate for your platform.
3. Use a managed PostgreSQL instance with adequate `DB_POOL_*` sizing
   (`pool_size + max_overflow` per process × replica count).
4. Confirm rate-limit and FSM behavior under load with Redis enabled.
5. Do **not** rely on in-memory rate limits or `MemoryStorage` across replicas.

## Backups

This repository does **not** automate PostgreSQL backups. Use your hosting
provider’s managed Postgres backup/restore (or `pg_dump` / PITR) for production.
