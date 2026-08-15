# Features follow-up (Russian, first-/start picker, i18n gaps)

This document covers the three gaps closed after
[`FEATURES.md`](FEATURES.md): Russian as a third locale, an explicit language
picker on first `/start`, and stored-language notices on rate-limit / global
error paths.

---

## Item 1 — Russian as a third supported language

**What was built**

- [`bot/locales/ru.py`](bot/locales/ru.py) is a `Texts` subclass of the Uzbek
  base, same shape as English, with natural Russian for every field.
- `BTN_LANG_RU` and a shared `START_LANGUAGE_PROMPT` were added to uz, en, and
  ru (no handler strings were found that bypassed `texts`).
- [`SUPPORTED_LANGUAGES`](bot/locales/__init__.py) is `{uz, en, ru}`.
  `normalize_language` maps `ru` / `ru-RU` via the existing primary-subtag rule.
- [`language_keyboard`](bot/keyboards/inline.py) is one row:
  `lang:uz` | `lang:ru` | `lang:en`.
- [`register_bot_commands`](bot/__main__.py) already iterates
  `(None, *sorted(SUPPORTED_LANGUAGES))`, so `ru` is included for
  `BotCommandScopeDefault` and per-admin `BotCommandScopeChat`.

**Files**

- [`bot/locales/ru.py`](bot/locales/ru.py) (new)
- [`bot/locales/uz.py`](bot/locales/uz.py), [`bot/locales/en.py`](bot/locales/en.py),
  [`bot/locales/__init__.py`](bot/locales/__init__.py)
- [`bot/keyboards/inline.py`](bot/keyboards/inline.py)
- [`tests/test_i18n.py`](tests/test_i18n.py), [`tests/test_help.py`](tests/test_help.py)

**Operator**

- Restart the bot so `set_my_commands` registers the Russian menu.
- No new env vars. No new Alembic revision (`users.language_code` already
  stores any supported code).

**Tests:** `normalize_language("ru")` / `"ru-RU"`; `get_texts("ru")`; `/language`
keyboard includes `lang:ru`; Russian `/help` and `GUIDANCE`; command
registration count is 8 (`None`, `en`, `ru`, `uz` × default + admin).

---

## Item 2 — First `/start` language picker

**What was built**

- New-user signal is the existing one: [`crud.get_user_language`](bot/db/crud.py)
  returns `None` when there is no `users` row (`language_code` is `NOT NULL`, so
  "no stored language" means "no row").
- First `/start` does **not** call `ensure_user` (that would insert a
  Telegram-inferred language and skip the picker). It sends
  `START_LANGUAGE_PROMPT` plus the shared `language_keyboard`.
- Returning users (`get_user_language` is a stored code) go straight to
  `WELCOME` as before.
- The `lang:` callback still persists via `set_user_language`. If the user had
  no row (`was_new`), it then sends the normal `/start` welcome in the chosen
  language. If they already had a row, it only edits to `LANGUAGE_UPDATED`.
- `/language` is unchanged and is **not** gated. After the first-start picker,
  the user can run `/language` any time and change language again.

**Prompt choice**

Trilingual `START_LANGUAGE_PROMPT` (identical in uz/en/ru):

`Tilni tanlang / Выберите язык / Choose a language:`

Why: the user has not chosen a locale yet, so a single-language prompt would
fail for two of three audiences. Button labels are already native names.
Keeping the string on `Texts` avoids a second i18n mechanism. `/language` still
uses locale-specific `LANGUAGE_CHOICE`.

**Files**

- [`bot/handlers/user.py`](bot/handlers/user.py)
- [`bot/locales/uz.py`](bot/locales/uz.py), [`bot/locales/en.py`](bot/locales/en.py),
  [`bot/locales/ru.py`](bot/locales/ru.py)
- [`tests/test_i18n.py`](tests/test_i18n.py)

**Operator:** none beyond restart (same as Item 1).

**Tests:** first `/start` shows picker and not `WELCOME`; selecting a language
stores it and then shows `WELCOME` in that language; returning `/start` skips
the picker; after the first-start picker, `/language` still changes to a
different locale.

---

## Item 3 — Rate-limit and error-handler stored language

**What was built**

- [`bot/locales/lookup.py`](bot/locales/lookup.py) `load_stored_language`:
  short-lived session, `get_user_language`, close; never raises.
- Called only when sending a user-facing notice (not on every allowed update).
- Rate-limit notices and the global error handler use
  `stored or telegram language_code`.
- The error handler wraps the lookup in its own `try/except` so a raising mock
  or unexpected failure cannot cause a second exception.

**Why a scoped lookup, not middleware reorder**

Order stays: rate limit → DB session → locale. Rate limit stays first so a
flood does not check out a pool connection per update. Locale cannot see a
stored preference without a session, so moving locale before the limiter would
not help unless DB moved too — which would change flood behaviour. A lookup
only on the rare notify/error path is the smaller, safer change.

**Files**

- [`bot/locales/lookup.py`](bot/locales/lookup.py) (new)
- [`bot/middlewares/rate_limit.py`](bot/middlewares/rate_limit.py)
- [`bot/__main__.py`](bot/__main__.py)
- [`tests/test_rate_limit.py`](tests/test_rate_limit.py),
  [`tests/test_error_handler.py`](tests/test_error_handler.py)

**Operator:** none.

**Tests:** stored Russian preference → Russian `RATE_LIMITED`; stored English
preference → English `GENERIC_ERROR`; lookup raising inside the error handler
still replies with the Telegram/default text.

---

## Verification

| Check | Result (this change set) |
|-------|--------------------------|
| `pytest -v` | **81 passed**, 7 skipped (Postgres CRUD when `TEST_DATABASE_URL` is unset) |
| `ruff check bot tests` | All checks passed |
| `mypy bot` | Success: no issues found in 35 source files |

Postgres-gated CRUD tests still skip unless `TEST_DATABASE_URL` is set (same as
before).

---

## Operator checklist

1. Restart the process (`python -m bot` or the container) so command menus
   include `ru` and the first-/start picker is live.
2. No new migrations. Existing `alembic upgrade head` (003 `language_code`) is
   enough.
3. Open a private chat with the bot from each admin account so
   `BotCommandScopeChat` can apply for Russian as well.
