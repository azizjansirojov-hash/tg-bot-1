# UPSERT FIX REPORT

**Date:** 2026-08-12  
**Closes:** `DOCKER_STACK_TEST_REPORT.md` NEW issues found #1  
**Scope:** Same-session ORM return staleness on `INSERT … ON CONFLICT … DO UPDATE … RETURNING`

---

## Root cause

With `expire_on_commit=False` (production session factory and the upsert test fixture), SQLAlchemy keeps loaded entities in the identity map across commits. A second `upsert_movie` / `upsert_user_activity` in the same session correctly updates the Postgres row via `ON CONFLICT DO UPDATE … RETURNING`, but without `populate_existing` the ORM reuses the already-mapped instance and **ignores RETURNING column values**, so the Python object keeps pre-update attributes (`title`, `request_count`, etc.). A fresh session always saw the correct row — this was identity-map staleness only, not a failed write.

---

## Fix applied

**File:** [`bot/db/crud.py`](bot/db/crud.py)

Only two `on_conflict_do_update` call sites exist in the repo; both were updated. SQL remains a single atomic upsert; no read-then-write path was introduced.

### `upsert_movie`

Added `.execution_options(populate_existing=True)` after `.returning(Movie)` so RETURNING refreshes the identity-mapped `Movie`.

### `upsert_user_activity`

Same pattern after `.returning(User)`.

```diff
         .returning(Movie)
+        .execution_options(populate_existing=True)
     )
```

```diff
         .returning(User)
+        .execution_options(populate_existing=True)
     )
```

No `session.refresh()` fallback was required — `populate_existing=True` alone fixed both failing tests.

---

## Test results

| Suite | Before (DOCKER_STACK_TEST_REPORT) | After |
|-------|-----------------------------------|--------|
| `pytest -v tests/test_crud_upsert.py` | 2 failed, 2 passed | **4 passed** |
| Full `pytest -v` (with `TEST_DATABASE_URL`) | 29 passed, 2 failed, 0 skipped | **31 passed, 0 skipped, 0 failed** |
| `ruff check .` | Pass | **Pass** (`All checks passed!`) |
| `mypy bot` | — | **Pass** (`Success: no issues found in 28 source files`) |

Previously failing tests now green:

- `test_upsert_movie_insert_and_overwrite`
- `test_upsert_user_activity_increments`

---

## Call-site audit

| Location | Call | Uses return value? | Production impact before fix |
|----------|------|--------------------|------------------------------|
| `bot/handlers/admin.py` `_save_movie` | `await crud.upsert_movie(...)` | **No** — return discarded | **None.** Success / confirm copy uses FSM / `_success_text(code, title, …)`, not the returned `Movie`. |
| `bot/handlers/user.py` `handle_movie_code` | `await crud.upsert_user_activity(session, user_id)` | **No** — return discarded | **None.** Activity is fire-and-forget; video path uses `get_movie_by_code`, not the returned `User`. |
| `bot/services/` | — | No call sites | — |
| `tests/test_crud_upsert.py` | Assigns return values | Yes | Tests only |

**Conclusion:** User-facing behavior was **not** wrong in production before this fix — call sites never read returned entity attributes. The bug was a **latent API contract risk** (and a hard fail for integration tests that correctly assert the returned object matches the post-update row).

---

## Cleanup

- `docker compose down` after verification.

---

## Not pushed yet

Local commit only (not pushed to remote):

```text
fix: resolve stale ORM return values on upsert with populate_existing
```
