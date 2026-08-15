# Telegram Movie-Code Bot

A production-ready Telegram bot: users send a numeric movie code, and the bot
replies with the matching video. Videos are **not** stored on the server —
they live in a private Telegram channel, and the bot delivers them by
`file_id`.

**Stack:** Python 3.11+, aiogram 3, SQLAlchemy 2 (async), PostgreSQL, Alembic,
pydantic-settings. Optional Redis for multi-replica FSM + rate limits.

---

## Features

- `/start` welcome + numeric code lookup → `send_video` (plain-text captions)
- `/help` (role-aware) and Telegram `/` command menu via `set_my_commands`
- `/language` — Uzbek (default) or English, stored per user
- Friendly guidance for non-numeric messages
- Dual-layer per-user rate limiting (code lookup + global ceiling) plus `/broadcast` cooldown
- Admin flow: forward a video from the storage channel → FSM asks for code & title
- `/list_codes`, `/delete_code`, `/stats`, `/auditlog`, `/broadcast`, `/cancel` for admins
- Polling mode (local) and webhook mode (Railway / Render)
- Optional Redis-backed FSM + rate limits (`USE_REDIS=true`)

---

## Local setup

### 1. Prerequisites

- Python **3.11+** (Docker image and lockfile target 3.11)
- PostgreSQL 14+ (or use `docker compose` for the database)
- Optional: Redis 7+ when testing `USE_REDIS=true`

### 2. Clone and create a virtualenv

```bash
git clone <your-repo-url>
cd tg-bot-1
python -m venv .venv

# Windows PowerShell
.venv\Scripts\Activate.ps1

# Linux / macOS
source .venv/bin/activate

pip install --require-hashes -r requirements.txt
pip install -r requirements-dev.txt   # for tests / lint
```

After `git pull`, re-run those two install commands so the venv matches the lockfile (CI already installs from hashes before tests).

### 3. Configure environment

```bash
cp .env.example .env
```

Edit `.env` and set at least:

| Variable | Description |
|----------|-------------|
| `BOT_TOKEN` | From [@BotFather](https://t.me/BotFather) |
| `DATABASE_URL` | `postgresql+asyncpg://USER:PASS@HOST:5432/DB` |
| `STORAGE_CHANNEL_ID` | Private channel ID (`-100…`) where the bot is admin |
| `ADMIN_IDS` | Comma-separated Telegram user IDs |
| `BOT_MODE` | `polling` for local development |

**Local Postgres credentials in compose / `.env.example` (`postgres`/`postgres`) are for local development only. Change them for any non-local use.**

Optional: start Postgres (and Redis) with Docker:

```bash
docker compose up -d db redis
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Run the bot (polling)

```bash
python -m bot
```

You should see logs like `Starting bot in polling mode`. Open the bot in
Telegram and send `/start`.

---

## Environment reference

| Variable | Required | Default | Notes |
|----------|----------|---------|-------|
| `BOT_TOKEN` | yes | — | BotFather token |
| `DATABASE_URL` | yes | — | Must use `postgresql+asyncpg://` |
| `STORAGE_CHANNEL_ID` | yes | — | `-100…` |
| `ADMIN_IDS` | yes | — | CSV of Telegram user IDs |
| `LOG_LEVEL` | no | `INFO` | |
| `BOT_MODE` | no | `polling` | `polling` \| `webhook` |
| `WEBHOOK_URL` | if webhook | — | Public HTTPS origin |
| `WEBHOOK_PATH` | no | `/webhook` | |
| `WEBHOOK_SECRET` | if webhook | — | ≥32 chars, not a weak default |
| `PORT` | no | `8080` | Webhook HTTP listen port |
| `RATE_LIMIT_MAX_REQUESTS` | no | `5` | Code lookups (non-admins) |
| `RATE_LIMIT_WINDOW_SECONDS` | no | `60` | |
| `RATE_LIMIT_GLOBAL_MAX_REQUESTS` | no | `60` | All updates (incl. admins) |
| `RATE_LIMIT_GLOBAL_WINDOW_SECONDS` | no | `60` | |
| `RATE_LIMIT_ABUSE_THRESHOLD` | no | `10` | WARNING after N blocks |
| `RATE_LIMIT_ABUSE_WINDOW_SECONDS` | no | `300` | |
| `RATE_LIMIT_MAX_TRACKED_USERS` | no | `10000` | In-memory map cap |
| `DB_POOL_SIZE` | no | `5` | |
| `DB_MAX_OVERFLOW` | no | `10` | |
| `DB_POOL_TIMEOUT` | no | `30` | |
| `DB_POOL_RECYCLE` | no | `1800` | |
| `USE_REDIS` | no | `false` | Shared FSM + rate limits. **Required** if more than one replica. |
| `REDIS_URL` | if Redis | `redis://localhost:6379/0` | Required when `USE_REDIS=true` |
| `BOT_REPLICA_COUNT` | no | `1` | If `>1` and `USE_REDIS=false`, startup **fails fast** |
| `BROADCAST_COOLDOWN_SECONDS` | no | `300` | Min seconds between admin `/broadcast` commands |

---

## Deploying with webhook mode (Railway / Render)

1. Deploy this repo (Dockerfile is ready). The container runs:

   ```text
   alembic upgrade head && python -m bot
   ```

   The image defaults to `BOT_MODE=webhook`. The HEALTHCHECK probes `/healthz` in
   webhook mode and exits 0 immediately in polling mode.

   HTTP probes (webhook server):

   - `GET /livez` — liveness (process up, no database call)
   - `GET /healthz` — readiness (`SELECT 1`, cached for a few seconds so the
     unauthenticated endpoint cannot hammer the pool)

2. Set environment variables on the platform (do **not** commit `.env`):

   | Variable | Value |
   |----------|--------|
   | `BOT_TOKEN` | your bot token |
   | `DATABASE_URL` | managed Postgres URL with `postgresql+asyncpg://` scheme |
   | `STORAGE_CHANNEL_ID` | `-100…` |
   | `ADMIN_IDS` | e.g. `123456789` |
   | `BOT_MODE` | **`webhook`** |
   | `WEBHOOK_URL` | public HTTPS origin (no trailing slash) |
   | `WEBHOOK_PATH` | `/webhook` (default) |
   | `WEBHOOK_SECRET` | long random string (≥32 chars) |
   | `PORT` | usually set automatically |
   | `LOG_LEVEL` | `INFO` |
   | `USE_REDIS` / `REDIS_URL` | **required** if running more than one replica (`BOT_REPLICA_COUNT>1` fails without Redis) |
   | `BOT_REPLICA_COUNT` | `1` unless you are actually scaling out |

3. Telegram will POST updates to `WEBHOOK_URL` + `WEBHOOK_PATH`.

Webhook mode with `USE_REDIS=false` is only safe for a **single** process. The bot logs a loud WARNING at startup in that configuration.

**Note:** If your host provides `postgres://…` URLs, change the scheme to
`postgresql+asyncpg://` before setting `DATABASE_URL`.

Production must use **strong unique** `DATABASE_URL` credentials, `WEBHOOK_SECRET`, and Redis auth if Redis is exposed. Never run [`docker-compose.yml`](docker-compose.yml) unmodified on a public host (it publishes Postgres/Redis with default passwords).

### Database backups

This repository does **not** automate PostgreSQL backups. Use your hosting
provider’s managed Postgres backup/restore (or `pg_dump` / PITR) for production.

---

## Alembic migrations

```bash
alembic upgrade head
alembic current
alembic downgrade -1
```

---

## Admin guide: how to add a new movie

You do **not** upload files to a server. Videos stay in your private Telegram
channel; the bot only stores a `file_id` and a code.

### One-time setup

1. Create a **private** Telegram channel (or use the existing one).
2. Add the bot as an **administrator** of that channel.
3. Put the channel’s numeric ID in `STORAGE_CHANNEL_ID` (starts with `-100`).
4. Put your Telegram user ID in `ADMIN_IDS`.

### Adding a movie (step by step)

1. Upload the video to the **storage channel**.
2. Open a **private chat** with the bot.
3. **Forward** that video message from the channel to the bot.
4. Enter a unique numeric code (example: `102`).
5. If the code exists, confirm overwrite or cancel.
6. Enter a title (max 255 characters), or `-` to skip.
7. Confirm save (Yes/No).

### Admin commands

| Command | What it does |
|---------|----------------|
| `/list_codes` | List all codes (10 per page, Prev/Next) |
| `/delete_code 102` | Delete a code (asks Yes/No first) |
| `/stats` | Total movies + unique requesting users |
| `/auditlog` | Paginated admin mutation audit log |
| `/cancel` | Abort the add-movie conversation mid-flow |

---

## Security & Scaling Notes

See **[SECURITY_HARDENING_REPORT.md](SECURITY_HARDENING_REPORT.md)** for:

- Rate-limit design (memory vs Redis)
- Why `MemoryStorage` / in-memory limits are **not** multi-replica safe
- Webhook secret rules
- Checklist before horizontal scaling (`USE_REDIS=true`)
- Audit-log retention SQL example

---

## Project structure

```text
bot/
  __main__.py          # polling / webhook entry
  config.py            # pydantic-settings
  handlers/            # Telegram interaction
  db/                  # models + crud
  middlewares/         # DB session + rate limit
  filters/             # IsAdmin
  states/              # FSM for add-movie
  keyboards/           # inline keyboards
  services/            # safe Telegram API wrappers
alembic/               # migrations
scripts/               # manual ops SQL
Dockerfile
docker-compose.yml
.env.example
```

---

## Security notes

- Never commit `.env` or real tokens.
- All secrets load from environment variables via pydantic-settings.
- The bot validates required settings on startup and fails fast if anything is missing.
- Only users in `ADMIN_IDS` can add, list, delete, view stats, or read the audit log.
- Dynamic titles in HTML messages are escaped; video captions use plain text.
- Production deployments must set strong unique credentials for Postgres, Redis, and `WEBHOOK_SECRET`. The compose defaults (`postgres`/`postgres`) and published ports are for **local development only**.
