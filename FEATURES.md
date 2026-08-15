# Features shipped (help, i18n, broadcast)

This document covers the three features added after the audit-fix work in
[`FIXES-FOLLOWUP.md`](FIXES-FOLLOWUP.md) and [`FIXES-MINOR.md`](FIXES-MINOR.md).
(`FIXES.md` is referenced by those files but is not in this repository.)

---

## Feature 1 — `/help` and BotFather / Telegram command menu

**What was built**

- A single command registry in [`bot/commands.py`](bot/commands.py) drives both
  `/help` text and `bot.set_my_commands(...)`. Descriptions are `Texts` field
  names, not duplicated strings.
- `/help` on the user router lists only commands the current user can use.
  Admins (via existing `Settings.is_admin` / `ADMIN_IDS`) also see the admin
  section.
- At startup, [`register_bot_commands`](bot/__main__.py) registers:
  - `BotCommandScopeDefault` — user commands
  - `BotCommandScopeChat` per admin Telegram ID — user + admin commands
  - After Feature 2, this is repeated for `language_code=None`, `en`, and `uz`

**Files**

- [`bot/commands.py`](bot/commands.py) (new)
- [`bot/handlers/user.py`](bot/handlers/user.py)
- [`bot/locales/uz.py`](bot/locales/uz.py) (and later `en.py`)
- [`bot/__main__.py`](bot/__main__.py)
- [`tests/test_help.py`](tests/test_help.py)

**Operator**

- Restart the bot so `set_my_commands` runs. **Do not** set commands in
  BotFather by hand; the Bot API overwrites the menu.
- Admin-specific menus use `BotCommandScopeChat`. The admin must have opened a
  **private chat** with the bot (chat id = user id) or Telegram may not apply
  that scope.

**Tests:** non-admin `/help` omits admin commands; admin id `111` sees the full
list; `set_my_commands` is mocked (no live Telegram).

---

## Feature 2 — Multi-language support

**What was already there (not replaced)**

Locale scaffolding was a Python `Texts` class in [`bot/locales/uz.py`](bot/locales/uz.py)
(not gettext `.po` / Fluent). Default language remains **Uzbek (Latin)**. English
was added as a sibling module, as the original comment suggested.

**What was built**

- [`bot/locales/__init__.py`](bot/locales/__init__.py): `SUPPORTED_LANGUAGES`,
  `DEFAULT_LANGUAGE = "uz"`, `normalize_language`, `get_texts`. Unknown codes
  (`fr`, `xx`) and `en-US` → primary subtag / fallback to `uz`. Never a missing-key
  placeholder.
- Alembic [`003_user_language`](alembic/versions/003_user_language.py):
  `users.language_code`.
- `ensure_user` on `/start`, `/help`, `/language` (does not bump `request_count`,
  does not overwrite a stored language). Code lookups still use
  `upsert_user_activity`.
- `/language` + inline keyboard (`lang:uz` / `lang:en`).
- `UserLocaleMiddleware` after the DB session injects `texts` from the stored
  preference, else Telegram `from_user.language_code`.
- Handler and keyboard strings use injected `texts` (default `TEXTS` for unit
  tests that call handlers directly).

**Files**

- [`bot/locales/en.py`](bot/locales/en.py), [`bot/locales/__init__.py`](bot/locales/__init__.py), [`bot/locales/uz.py`](bot/locales/uz.py)
- [`bot/middlewares/locale.py`](bot/middlewares/locale.py)
- [`bot/db/models.py`](bot/db/models.py), [`bot/db/crud.py`](bot/db/crud.py)
- [`bot/handlers/user.py`](bot/handlers/user.py), [`bot/handlers/admin.py`](bot/handlers/admin.py)
- [`bot/keyboards/inline.py`](bot/keyboards/inline.py)
- [`bot/middlewares/rate_limit.py`](bot/middlewares/rate_limit.py), [`bot/__main__.py`](bot/__main__.py)
- [`tests/test_i18n.py`](tests/test_i18n.py), [`tests/test_crud_upsert.py`](tests/test_crud_upsert.py)

**Env vars:** none required.

**Operator:** `alembic upgrade head` (includes 003 and 004).

**i18n coverage (honest)**

User-facing strings in handlers, admin flows, and keyboards go through `texts` /
`get_texts`. Two exceptions use Telegram `language_code` only (no DB row yet /
no session):

- Rate-limit notices in [`bot/middlewares/rate_limit.py`](bot/middlewares/rate_limit.py)
  (middleware runs **before** the DB + locale middlewares).
- The global error handler in [`bot/__main__.py`](bot/__main__.py).

Follow-up if needed: pass stored language into those paths (would require
reordering middleware or a cached lookup).

---

## Feature 3 — Admin broadcast

**What was built**

- Admin-only `/broadcast` FSM (same `IsAdmin` router filter as other admin
  commands). Non-admins hit the existing denial handler.
- **Text-only v1** (`parse_mode=None`). Media broadcast was deferred: the bot's
  content model is storage-channel `file_id` videos, and mass `send_video` would
  multiply flood risk. No recipient filters beyond **active users**.
- Confirmation with **N from SQL** (`count_broadcast_recipients`). No
  `send_message` until Yes. No / cancel via `/cancel` or the No button.
- Paced send (~25 messages/second) in [`bot/services/broadcast.py`](bot/services/broadcast.py).
  `TelegramRetryAfter` sleeps `retry_after` and retries that chat once.
  `TelegramForbiddenError` skips the user, records them, and continues.
  Blocked users are marked `is_active=False`.
- `/broadcast` cooldown via the existing rate-limit backend, key
  `broadcast:{user_id}`, `max_requests=1`, window
  `BROADCAST_COOLDOWN_SECONDS` (default 300). Confirm callbacks are not limited
  by this layer.
- Audit log `action=broadcast` with counts and duration only (**no message
  body**). Summary is sent to the admin.

**Files**

- [`bot/handlers/admin.py`](bot/handlers/admin.py), [`bot/states/admin_broadcast.py`](bot/states/admin_broadcast.py)
- [`bot/services/broadcast.py`](bot/services/broadcast.py)
- [`bot/middlewares/rate_limit.py`](bot/middlewares/rate_limit.py), [`bot/config.py`](bot/config.py)
- [`alembic/versions/004_user_is_active.py`](alembic/versions/004_user_is_active.py)
- [`tests/test_broadcast.py`](tests/test_broadcast.py)
- [`.env.example`](.env.example), [`README.md`](README.md)

**Env:** optional `BROADCAST_COOLDOWN_SECONDS` (default 300).

**Operator:** `alembic upgrade head`; restart the bot.

**Deferred**

- Broadcast of photos/videos/forwards
- Filtered subsets (e.g. active in last N days)
- Re-activating users who unblock the bot (no inbound "unblocked" event is
  handled)

---

## Verification

| Check | Result (this change set) |
|-------|--------------------------|
| `pytest -v` | **68 passed**, 7 skipped (Postgres CRUD when `TEST_DATABASE_URL` is unset) |
| `ruff check bot tests` | All checks passed |
| `mypy bot` | Success: no issues found in 33 source files |

Postgres-gated CRUD tests still skip unless `TEST_DATABASE_URL` is set (same as
before). New language/`is_active` assertions live in those tests when the DB is
available.

---

## Operator checklist

1. `alembic upgrade head` (003 `language_code`, 004 `is_active`).
2. Restart the process (`python -m bot` or the container) so command menus
   register.
3. Optionally set `BROADCAST_COOLDOWN_SECONDS`.
4. Open a private chat with the bot from each admin account so
   `BotCommandScopeChat` can apply.
