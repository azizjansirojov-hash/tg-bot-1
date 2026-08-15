# DEBUG-STEPTHROUGH-REPORT

Deep internal-state verification of the aiogram 3 / async SQLAlchemy / Redis
Telegram bot. This pass executed real dispatcher updates against live
Postgres (`localhost:5432/tgbot`) and live Redis (`localhost:6379`), with
temporary NDJSON instrumentation at the points named in the brief. All
temporary instrumentation was removed afterward.

**Prior docs:** `DEBUG-REPORT.md`, `FEATURES.md`, and `FEATURES-FOLLOWUP.md`
were **not present in the workspace** at the start of this pass (only
`README.md` existed). Claims about middleware order, language fallback, and
the untested add-movie flow are taken from this task brief and from the
current source, not from those files.

**How triggers were run:** a harness imported `_build_dispatcher()`, fed
constructed `Update` objects through `Dispatcher.feed_update` against a
`Bot` with a capturing session (no live Bot API). Postgres and Redis were
real. Telegram I/O was stubbed except where a fake `Bot.send_message` was
used to raise `TelegramRetryAfter` / `TelegramForbiddenError` into the real
`send_broadcast` loop.

---

## Session 1 — Middleware order and state handoff

**Instrumented:** entry/exit of `RateLimitMiddleware.__call__`,
`DbSessionMiddleware.__call__`, `UserLocaleMiddleware.__call__`, and the
`/start` handler branch (`bot/handlers/user.py`). Logged `id(session)`,
whether `texts` existed yet, stored language, and `texts.WELCOME` prefix.

**Trigger:** `Update` with `/start` from telegram id `91002`, who already had
`users.language_code = 'en'` in Postgres. Telegram `language_code` on the
update was `'uz'` (deliberate mismatch).

**Observed (seq 1–6, `debug-1efe1c.log`):**

1. `rate_limit.py:__call__:entry` — `has_texts=false`, `session_id=140735742356288`
   (`id(None)`; session not injected yet)
2. `rate_limit.py:__call__:exit` — same `session_id`
3. `db.py:__call__:entry` — `session_id=2455220406544`, `session_active=true`,
   `has_texts=false`
4. `locale.py:__call__:handoff` — `session_id=2455220406544`,
   `session_is_data_session=true`, `stored="en"`, `telegram_code="uz"`,
   `welcome_prefix="👋 Welcome!\n\nSend a movie"`
5. `user.py:cmd_start:branch` — **same** `session_id=2455220406544`,
   **same** `texts_id=2455208806352`, `welcome_prefix` English, `branch="returning"`
6. `db.py:__call__:exit` — same session still active

**Verdict: CONFIRMED.** Runtime order is rate limit → DB session → locale →
handler. The handler received the same `AsyncSession` object locale used.
`texts` at handler time was English (`WELCOME` starts with `"👋 Welcome!"`),
not Uzbek, matching the stored preference over Telegram `language_code`.

---

## Session 2 — First-`/start` new-vs-returning branch

**Instrumented:** exact `get_user_language` result at the new/returning
branch in `cmd_start`. Direct SQL `SELECT count(*) FROM users WHERE
telegram_id = :tid` immediately after the picker reply, before any callback.

**Triggers:**

- New: telegram id `91001`, no DB row, `language_code="ru"`
- Returning: telegram id `91002`, stored `"en"`

**Observed:**

- New user (seq 11): `"stored": null`, `"stored_is_none": true`,
  `"branch": "new_user_picker"`
- Postgres after picker, before tap (seq 13): `"telegram_id": 91001,
  "row_count": 0`
- Returning (seq 18): `"stored": "en"`, `"stored_is_none": false`,
  `"branch": "returning"`

**Verdict: CONFIRMED.** `get_user_language` is `None` for a missing row and
`"en"` for a stored language. No `users` INSERT happens before the new user
picks a language.

---

## Session 3 — Redis rate-limiter atomicity under concurrency

**Instrumented:** immediately before/after Lua `EVAL` in
`RedisRateLimitBackend.is_limited`, plus a live `ZCARD` on `rl:hits:{key}`
right after each script return, and a final `ZCARD` after `asyncio.gather`.

**Trigger:** 20 concurrent `is_limited("stepthrough:concurrency", window=60,
max_requests=5)` calls against real Redis 7.

**Observed (seq 60):**

```
allowed=5, blocked=15, max_requests=5, zcard_final=5
results_limited_flags = [false×5, true×15]
```

Individual script returns: five `script_return=0` (allow), fifteen
`script_return=1` (block). Every blocked call's post-EVAL `zcard_after` was
`5`. Allowed calls' post-EVAL `ZCARD` ranged 3–5 because that extra `ZCARD`
is **not** inside the Lua script (other EVALs can complete between `EVAL`
return and `ZCARD`); that does not contradict the script decision. Final
key cardinality was exactly `max_requests`.

**Verdict: CONFIRMED.** Allowed count matches `max_requests` exactly (not
off-by-one). No call was allowed after Redis already held 5 members; no
blocked call's script return disagreed with a final window of 5.

---

## Session 4 — Broadcast pacing and failure handling

**Instrumented:** `send_broadcast` loop before/after each recipient;
`TelegramRetryAfter` catch (logged `retry_after`, then sleep, then retry);
`TelegramForbiddenError` catch; `asyncio.sleep` seconds; Postgres
`is_active` before/after `mark_users_inactive` (same path the admin handler
uses after `send_broadcast`).

**Trigger:** real users `91021` (ok first), `91022` (RetryAfter 2s then
success), `91023` (Forbidden), `91024` (ok last). Fake `bot.send_message`
raised into the **real** `_send_one`. Sleeps were recorded then no-op'd so
the test did not wait 2 wall-clock seconds; the value passed to
`asyncio.sleep` was logged.

**Observed:**

- Before: all four `is_active=true` (seq 61)
- Index 0 / `91021`: outcome `ok`, `succeeded=1` (seq 63)
- `91022`: `retry_after=2`, `exc_type=TelegramRetryAfter` (seq 66);
  `asyncio.sleep` called with `seconds=2` (seq 67); then
  `retry_ok` for **the same** `chat_id=91022` (seq 68); outcome `ok`,
  `succeeded=2` (seq 69) — did not skip
- `91023`: Forbidden, outcome `blocked`, loop continued (seq 72–73)
- Index 3 last / `91024`: `is_last=true`, outcome `ok`, `succeeded=3`,
  `failed_blocked=1` (seq 75–76)
- After `mark_users_inactive`: `91021=true, 91022=true, 91023=false,
  91024=true` (seq 78)
- Totals: `attempted=4, succeeded=3, failed_blocked=1, failed_other=0,
  blocked_ids=[91023]`
- Sleeps: `[0.01, 2, 0.01, 0.01, 0.01]` — flood wait is exactly
  `retry_after=2`; `0.01` is the pacing delay at `sends_per_second=100`

**Verdict: CONFIRMED.** Exact `retry_after` sleep, retry of the same
recipient, Forbidden does not abort the batch, only that user is marked
inactive, counters are correct at first and last index.

---

## Session 5 — Global error handler language fallback

**Instrumented:** `unhandled_error_handler` chosen reply language;
`load_stored_language` `except` with the actual exception object.

**Triggers:** `/help` patched to raise `RuntimeError("forced-handler-error")`
through the live dispatcher for (1) stored `en` user `91011` with Telegram
`uz`, (2) no-row user `91012` with Telegram `ru`. (3) Direct
`unhandled_error_handler` with `crud.get_user_language` forced to raise
`RuntimeError("forced-load_stored_language-failure")` for `91013`
(Telegram `en`).

**Observed:**

- Stored (seq 83): `"stored": "en"`, `"telegram_language_code": "uz"`,
  `"chosen": "en"`, `"error_text_prefix": "Something went wrong. Please try again i"`
- None (seq 88): `"stored": null`, `"telegram_language_code": "ru"`,
  `"chosen": "ru"`, Russian prefix `"Что-то пошло не так. Пожалуйста, попробу"`
- Forced lookup failure (seq 89): caught
  `RuntimeError('forced-load_stored_language-failure')` **inside**
  `load_stored_language`; handler then (seq 90) `"stored": null`,
  `"chosen": "en"` (Telegram `language_code`); (seq 91) `"escaped": false`.
  The error handler's own `except` around `load_stored_language` did **not**
  fire — the lookup function swallowed the exception as designed
  ("Never raises").

**Verdict: CONFIRMED.** Fallback is stored → Telegram `language_code` →
(implicit default if both missing). A failure inside
`load_stored_language` does not escape as a second exception; the reply
falls through to Telegram `language_code`.

---

## Session 6 — Atomic delete-by-code

**Instrumented:** `crud.delete_movie` return value; handler branch in
`delete_code_callback`; direct `SELECT` on `movies` between calls.

**Triggers:**

1. Insert code `424201`, call `delete_movie` twice on separate sessions
   (committed), query Postgres between them.
2. Re-insert, feed two `delete:yes:424201` callbacks as admin `111`
   through the dispatcher.

**Observed:**

- First CRUD: `"deleted": true` (seq 92); between: `"rows": []` (seq 93)
- Second CRUD: `"deleted": false` (seq 94–95)
- First handler: `"branch": "ADMIN_DELETE_SUCCESS"` (seq 101)
- Second handler: `"deleted": false`, `"branch": "ADMIN_DELETE_ALREADY_GONE"`
  (seq 108) — the handler actually took that branch, not inferred from
  return value alone

**Verdict: CONFIRMED.** First delete removes the row; second returns
`False` and the handler uses `ADMIN_DELETE_ALREADY_GONE`.

---

## Session 7 — Admin add-movie flow (untested in the prior black-box pass)

**Real trigger (from source, not guessed):** there is no `/add_movie`
command. The flow starts at `admin_forward_video` when an **admin** sends a
**video** in a **private** chat with `StateFilter(None)` and
`extract_storage_forward` succeeds (Bot API 7+ `MessageOriginChannel` with
`chat.id == STORAGE_CHANNEL_ID`, or legacy `forward_from_chat`).

**Approximation label:** this environment cannot receive a live forwarded
post from a real Telegram channel (no live bot token / channel). Updates
were constructed as `Message` + `Video` + `MessageOriginChannel(chat.id=
-1001234567890, message_id=…)`. That exercises the same handler and
`extract_storage_forward` path used in unit tests. A human still needs to
verify with a real forward from the configured storage channel: Telegram
payload shape (`forward_origin` vs legacy fields), `file_id` usability for
later `send_video`, and that the bot is an admin of that channel.

### 7.1 Happy path

**Observed FSM (seq 114–135):**

| Step | FSM state | Stored data |
|------|-----------|-------------|
| After constructed forward | `AdminAddMovie:waiting_for_code` | `file_id=…-001`, `channel_message_id=9001`, `overwrite=false` |
| After code `88001` | `waiting_for_title` | plus `code=88001` |
| After title `Stepthrough Film` | `confirming_save` | plus `title=Stepthrough Film` |
| After `save:yes` | `None` | cleared |

Postgres after save (seq 135):

```
code=88001, title=Stepthrough Film,
file_id=BAACAgIAAxkBAAI-stepthrough-file-id-001, channel_message_id=9001
```

Matches what was entered. **CONFIRMED** (under constructed-forward
approximation).

### 7.2 Re-add existing code (upsert)

Second forward with `file_id=…-002`, `channel_message_id=9002`, same code
`88001` → `confirming_overwrite` (seq 146) → `overwrite:yes` sets
`overwrite=true` (seq 152) → title `Overwritten Title` → `save:yes`.

Postgres (seq 166): **`row_count=1`**,
`title=Overwritten Title`, `file_id=…-002`, `channel_message_id=9002`.
No duplicate row. **CONFIRMED.**

### 7.3 Abandoned mid-FSM — BUG FOUND, then fixed

**Repro (pre-fix):** admin starts add-movie (waiting_for_code), sends
non-digit text `not-a-code`, then `/cancel`.

**Actual vs expected (seq 183, `runId=pre`):**

| | Actual | Expected |
|---|---|---|
| Handler | `admin_cancel_fsm` **never ran** (no log) | `admin_cancel_fsm` clears FSM |
| `state_after_cancel` | `"AdminAddMovie:waiting_for_code"` | `None` |
| `data_after_cancel` | `{file_id, channel_message_id, overwrite}` | `{}` |

**Cause:** `admin_receive_code` was registered as
`AdminAddMovie.waiting_for_code, F.text` **before**
`StateFilter(AdminAddMovie, AdminBroadcast), Command("cancel")`.
`/cancel` is text, so it was handled as an invalid code
(`ADMIN_CODE_DIGITS_ONLY`) and the FSM stayed put. Same trap on
`waiting_for_title`. Broadcast already used `~F.text.startswith("/")`.

**File:** `bot/handlers/admin.py` (`admin_receive_code` /
`admin_receive_title` filters). Analogous to the earlier non-admin
`/cancel` miss: the cancel **handler existed**, but another handler won.

**Fix:** add `~F.text.startswith("/")` to both add-movie text handlers
(same pattern as `broadcast_receive_text`). Regression test:
`tests/test_admin_fsm.py::test_cancel_clears_waiting_for_code_not_swallowed_as_code`.

**Post-fix (`runId=post-fix`, seq 182–184):**

- `admin.py:admin_cancel_fsm`: `state_before=AdminAddMovie:waiting_for_code`,
  `state_after=None`
- `state_after_unexpected` still `waiting_for_code` (invalid text correctly
  stays in state)
- `state_after_cancel=None`, `data_after_cancel={}`
- Movie row for `88001` unchanged (no partial/garbage insert)

**Verdict after fix: CONFIRMED** for abandon + `/cancel`. Unexpected
non-command text does not write a row (confirmed both runs).

### 7.4 Non-admin trigger

Non-admin `999001` constructed the same channel-forward video.

**Observed (seq 189 / post-fix 190):** `"state": "None"`, `"data": {}`.
`admin_forward_video` never logged a start. No FSM was set.

Unlike `/list_codes` etc., there is **no** `ADMIN_ONLY` reply: the admin
router's `IsAdmin` filter drops the update, and user handlers do not match
a video. Silent ignore, not the command-denial text.

**Verdict: CONFIRMED** that the flow is not started for non-admins.
**Observation (not patched):** user-visible rejection is not the same
`ADMIN_ONLY` string used for admin commands. Product decision if a reply
is desired.

---

## Instrumentation cleanup and tests

- All `#region agent log` blocks, `bot/_agent_debug_log.py`, and the
  temporary harness/strip scripts were removed.
- Production leftover from instrumentation (`zcard_after`, unused
  `except as`, `enumerate` index, unused `before` state) was reverted.
- Lasting code changes: `/cancel` filter fix in `bot/handlers/admin.py`;
  regression test; `Command(...)` wrap in `bot/handlers/user.py` for E501.

**`ruff check bot tests`:** All checks passed.

**`pytest`:** 81 passed, 7 skipped, **1 failed** —
`tests/test_startup.py::test_webhook_without_redis_logs_warning` asserts
`aiohttp==3.14.x` but this venv has `aiohttp==3.13.3`. That is an
environment pin mismatch (`requirements.txt` specifies `aiohttp==3.14.3`),
not a regression from this pass. The new cancel test passed.

---

## What this pass caught that a black-box reply-text pass can miss

Sessions 1–6 **confirmed** the internal claims (middleware order, same
session object, no pre-picker INSERT, Redis Lua exact `max_requests`,
broadcast retry/sleep/inactive flag/counters, error-handler language
chain, atomic delete + `ADMIN_DELETE_ALREADY_GONE` branch). Those would
look "correct" from final reply text alone; the traces show they are
correct for coincidental-looking reasons **and** for the actual state.

Session 7 (explicitly untested before) found a **real bug**: `/cancel`
during add-movie `waiting_for_code` / `waiting_for_title` was swallowed as
invalid text, leaving FSM stuck. Final user text (`ADMIN_CODE_DIGITS_ONLY`)
looks like a validation message, not a stuck session — easy to miss in a
black-box pass that only checks `/cancel` outside those states or only
checks non-admin denial. That is the one defect this step-through
surfaced; it is fixed and re-verified with logs.
