# Debug / E2E verification report

This pass exercised the bot against **real Postgres 16** and **real Redis 7**
(`docker compose up -d db redis`, both already healthy). There is **no valid
BotFather token and no storage channel** in this environment, so Telegram's
network API was not called. Handler behavior was driven with constructed
`Update` / `Message` / `CallbackQuery` objects through `Dispatcher.feed_update`,
with a recording fake Bot session.

**Docs present in the repo:** [`README.md`](README.md), [`FEATURES.md`](FEATURES.md),
[`FEATURES-FOLLOWUP.md`](FEATURES-FOLLOWUP.md).
**Not in this repository** (so they could not be re-read here): `AUDIT.md`,
`FIXES.md`, `FIXES-FOLLOWUP.md`, `FIXES-MINOR.md`.

**Evidence legend**

| Tag | Meaning |
|-----|---------|
| **REAL-INFRA** | Observed against running Postgres and/or Redis in this session |
| **DISPATCHER** | Real handlers + middleware + DB/Redis; Telegram I/O mocked |
| **IN-PROCESS** | Direct call of Settings / handlers / HTTP app, no Telegram |
| **CODE-ONLY** | Not used as a pass criterion |

---

## A. First-contact flow

### 1. New user `/start` shows picker, not welcome — **PASS** (DISPATCHER + REAL-INFRA)

Fed `/start` from telegram id `501` with no `users` row. Reply was
`START_LANGUAGE_PROMPT` (`Tilni tanlang / Выберите язык / Choose a language:`).
Welcome strings were absent. `get_user_language(501)` was still `None`.

### 2. Each language button stores code and shows welcome — **PASS** (DISPATCHER + REAL-INFRA)

Three new users (`601`/`602`/`603`) tapped `lang:uz`, `lang:en`, `lang:ru`.
Postgres stored the matching `language_code`. The follow-up text contained the
Uzbek / English / Russian `WELCOME` respectively.

### 3. Returning `/start` skips picker — **PASS** (DISPATCHER + REAL-INFRA)

User `602` (stored `en`) sent `/start` again. English `WELCOME` only; no picker.

---

## B. Language switching

### 4. `/language` then a different locale — **PASS** (DISPATCHER + REAL-INFRA)

User `602` (English) ran `/language` (English `LANGUAGE_CHOICE` + three buttons),
tapped `lang:ru`. DB became `ru`. Next `/help` used Russian `HELP_HEADER`.

### 5. Switch twice more — **PASS** (DISPATCHER + REAL-INFRA)

`ru` → `uz` → `en`. Final `/help` was English. No stuck locale.

---

## C. `/help` and command menu

### 6. Non-admin `/help` — **PASS** (DISPATCHER)

English help for user `602`: `/start`, `/help`, `/language` present;
`/list_codes` and admin header absent.

### 7. Admin `/help` — **PASS** (DISPATCHER)

Admin id `111` (`ADMIN_IDS`): admin header plus `/list_codes`, `/delete_code`,
`/stats`, `/auditlog`, `/broadcast` (and `/cancel` in the command registry).

### 8. `set_my_commands` at registration — **PASS** (DISPATCHER)

Called `register_bot_commands(bot)` on the recording session. **8**
`setMyCommands` payloads: `language_code` `None` (×2 scopes), `en`, `ru`, `uz`
(default + `BotCommandScopeChat` for admin `111`).

**Not verified:** whether Telegram actually displays those menus in a client
(needs a real token).

---

## D. Core movie-code lookup

### 9. Valid code — **PASS** (DISPATCHER + REAL-INFRA)

Inserted movie `102` / `file_id=file-102`. User `602` sent `102`. Session recorded
`sendVideo` with `video=file-102`, `caption=Matrix`. `users.request_count` became
`1`.

**Not verified:** Telegram actually delivering that `file_id` (needs a real
storage-channel file).

### 10. Invalid input — **PASS** (DISPATCHER)

`not-a-code` → English `GUIDANCE`. `99999` → English `CODE_NOT_FOUND`. No crash.

---

## E. Admin functionality

### 11. `/list_codes` and `/auditlog` pagination — **PASS** (DISPATCHER + REAL-INFRA)

12 movies (PER_PAGE=10). Page 0 markup: only `list_codes:1` (no Prev). Page 1:
only `list_codes:0` (no Next). 12 audit `seed` rows: both pages contained `seed`.

Out-of-range callbacks (`list_codes:99`, `list_codes:-1`) were fed; the handler
clamps `page < 0` to `0` and `page >= total_pages` to the last page (no crash).

### 12. `/delete_code` atomic already-gone — **PASS** (DISPATCHER + REAL-INFRA)

`/delete_code 777` → confirm → `delete:yes:777` → success text and row gone.
Second `delete:yes:777` → English `ADMIN_DELETE_ALREADY_GONE` (not a generic
error).

### 13. Non-admin admin commands — **PASS** after a one-line fix (DISPATCHER)

`/list_codes`, `/delete_code`, `/stats`, `/auditlog`, `/broadcast` already
returned English `ADMIN_ONLY`.

**Bug found (fixed in this session):** `/cancel` was **not** in
`admin_commands_denied` (`bot/handlers/user.py`). A non-admin `/cancel` produced
**no reply** (admin router `IsAdmin` skipped it; user router ignored it).

**Change:** added `"cancel"` to that `Command(...)` list. Re-ran the same
dispatcher check: `/cancel` now returns `ADMIN_ONLY` like the others. Admin
`/cancel` is unchanged (admin router is registered first and still matches
admins).

---

## F. Rate limiting

### 14. Limit kicks in, stored-language notice, window recovers — **PASS** (REAL-INFRA)

`RateLimitMiddleware` + `RedisRateLimitBackend` against docker Redis. User `701`
had `language_code=ru` in Postgres; Telegram `language_code` was `en`. Global
ceiling 3 / 5s: 3 requests blocked; notice was Russian `RATE_LIMITED` (not
English). After 6s, a request was allowed again.

(Dispatcher-wide global ceiling was left high so earlier flows were not
starved; this check used a dedicated Redis-backed middleware instance.)

### 15. Redis Lua sliding window under concurrency — **PASS** (REAL-INFRA)

This session:

- `pytest tests/test_rate_limit.py` with Redis up: including
  `test_real_redis_lua_script_loads` and
  `test_real_redis_lua_does_not_overshoot_under_concurrency` — **passed**.
- Direct `RedisRateLimitBackend.is_limited` ×25 concurrent, max=5: **allowed=5,
  blocked=20**.

---

## G. Admin broadcast

### 16. Confirm, Forbidden, RetryAfter, audit, `is_active` — **PASS** (DISPATCHER + REAL-INFRA)

Admin `/broadcast` → body `UNIQUE_BODY_XYZ` → `broadcast:yes`. Recipients were
all active users (7), not a hand-picked three.

Fake session: chat `8002` → `TelegramForbiddenError`; `8003` → one
`TelegramRetryAfter(1)` then success. Logs: skipped blocked `8002`, flood wait
`8003`. Audit `details`:
`{"attempted":7,"succeeded":6,"failed_blocked":1,"failed_other":0,"duration_ms":...}`
— **message body not stored**. User `8002` `is_active=False`; `8003` stayed
active.

### 17. Broadcast cooldown — **PASS** (DISPATCHER + REAL-INFRA)

Immediate second `/broadcast` after G16: English
`RATE_LIMITED` with **3 seconds** (`BROADCAST_COOLDOWN_SECONDS=3` in the harness).
After 4s: `ADMIN_BROADCAST_ASK` again.

### 18. Non-admin cannot `/broadcast` — **PASS** (DISPATCHER)

User `602` `/broadcast` → `ADMIN_ONLY`. Admin router `IsAdmin` also rejects
id 602 (confirmed via existing `IsAdmin` unit test + this feed).

---

## H. Error handling and probes

### 19. Global error handler — **PASS** (DISPATCHER)

Patched `format_help_text` to raise `RuntimeError("injected e2e failure")`.
Dispatcher logged `Unhandled handler error user_id=602 ... RuntimeError`. User
received English `GENERIC_ERROR`. Process continued (later checks still ran).

### 20. `/livez` and `/healthz` cache — **PASS** (REAL-INFRA + IN-PROCESS)

`livez_handler` → 200, no DB. `healthz_handler` against real Postgres: first
call `connect()` once; two more calls inside the 5s window → still **1**
connect. Webhook smoke (check 22) also got HTTP 200 from `/livez` and `/healthz`
on a bound port.

---

## I. Startup / config

### 21. Invalid config fails fast — **PASS** (IN-PROCESS)

Constructed `Settings` + `validate_webhook_config()`:

- `WEBHOOK_URL=http://example.com` → `ValueError` containing `https://`.
- `BOT_REPLICA_COUNT=2`, `USE_REDIS=false` → `ValidationError` mentioning
  `BOT_REPLICA_COUNT`.

Also `pytest tests/test_config.py` (same rules) — all passed this session.

### 22. Polling / webhook start — **PASS** with stated limits (IN-PROCESS + REAL-INFRA)

- Polling: `run_polling` invoked `delete_webhook` + `start_polling` on mocks.
  **No live `getUpdates`.**
- Webhook: `run_webhook` on an ephemeral port, `set_webhook` mocked, **real
  Postgres** `/healthz` 200 and `/livez` 200.

`alembic upgrade head` on a **clean** schema: 001→004 succeeded. On a dirty DB
(pytest CRUD `drop_all` left `alembic_version` at 002 without `users`):
`003_user_language` failed with `relation "users" does not exist`. That is an
operator/test-isolation issue, not a runtime bot bug. Workaround: `DROP SCHEMA
public CASCADE` then `alembic upgrade head`.

---

## Summary table

| # | Check | Status | Evidence |
|---|--------|--------|----------|
| 1 | First `/start` picker | PASS | DISPATCHER + Postgres |
| 2 | uz/en/ru picker → welcome | PASS | DISPATCHER + Postgres |
| 3 | Returning `/start` | PASS | DISPATCHER + Postgres |
| 4 | `/language` change + `/help` | PASS | DISPATCHER + Postgres |
| 5 | Two further switches | PASS | DISPATCHER + Postgres |
| 6 | Non-admin `/help` | PASS | DISPATCHER |
| 7 | Admin `/help` | PASS | DISPATCHER |
| 8 | `set_my_commands` × langs/scopes | PASS | Recording Bot session |
| 9 | Valid movie code + activity | PASS | DISPATCHER + Postgres |
| 10 | Bad input guidance | PASS | DISPATCHER |
| 11 | list/audit pagination | PASS | DISPATCHER + Postgres |
| 12 | Delete + already-gone | PASS | DISPATCHER + Postgres |
| 13 | Non-admin admin commands | PASS | DISPATCHER (after `/cancel` fix) |
| 14 | Rate limit + stored ru + window | PASS | Redis + Postgres + middleware |
| 15 | Redis Lua concurrency | PASS | Real Redis |
| 16 | Broadcast + forbidden/retry/audit | PASS | DISPATCHER + Postgres |
| 17 | Broadcast cooldown | PASS | DISPATCHER + Redis |
| 18 | Non-admin `/broadcast` | PASS | DISPATCHER |
| 19 | Unhandled error reply | PASS | DISPATCHER |
| 20 | livez/healthz cache | PASS | Real Postgres |
| 21 | https / replica config fail-fast | PASS | Settings() |
| 22 | Polling/webhook start smoke | PASS | Mock Telegram + real /healthz |

Also this session: `pytest` with `TEST_DATABASE_URL` and Redis —
`tests/test_crud_upsert.py`, `test_rate_limit.py`, `test_config.py`,
`test_healthz.py`, `test_startup.py` — **34 passed**.

---

## Still needs a real Telegram token (staging)

1. BotFather token, `deleteWebhook` / polling or a public HTTPS webhook.
2. Command menu as shown in the Telegram client for `en` / `ru` / `uz` and
   per-admin private chat.
3. Real `send_video` using a `file_id` from the configured storage channel.
4. Admin **add-movie FSM** (forward from the storage channel) — not in the 22
   checks above.
5. Users who block/unblock the bot in a real chat (we simulated Forbidden).
6. Multi-replica `BOT_REPLICA_COUNT>1` with shared Redis in deployment.

---

## Change made during this pass

- [`bot/handlers/user.py`](bot/handlers/user.py): `admin_commands_denied` now
  includes `cancel`, so non-admins get the same `ADMIN_ONLY` reply as other
  admin commands. Trivial, consistent with the existing denial handler.

---

## Overall assessment

**Staging-ready, not fully production-proven without a live Telegram dry-run.**

All 22 listed checks passed in this session at DISPATCHER and/or REAL-INFRA
level. The only product bug found (`/cancel` silent for non-admins) was fixed
and re-verified. Remaining risk is almost entirely the Telegram network and
ops path (token, channel `file_id`, webhook TLS, replica topology), plus
keeping Alembic history consistent if someone runs CRUD tests that `drop_all`
on the same database used for migrations.
