# Audit follow-up (gaps from FIXES.md)

Closes the three unresolved items called out in [`FIXES.md`](FIXES.md). This environment **did** have Docker Desktop; Redis 7 and Postgres 16 were started with `docker compose up -d redis db`. GitHub Actions itself was **not** executed here.

---

## 1. Redis rate-limiter Lua vs a real Redis EVAL

**Status:** Fixed and verified against a real Redis 7 container.

**Change:** Added two tests that use `redis.asyncio.Redis` + `register_script` / `EVAL` on the production `_RL_SLIDING_WINDOW_LUA` string (not the in-process fake):

- `test_real_redis_lua_script_loads` — script loads and returns `0` (allowed) for an empty key; a Lua syntax error would fail this test.
- `test_real_redis_lua_does_not_overshoot_under_concurrency` — `asyncio.gather` of `max_requests + 20` calls; allowed count is exactly `max_requests`; `ZCARD` on the real key matches. Keys use a unique UUID suffix and are `DELETE`d in `finally`.

If Redis is unreachable, the `real_redis` fixture **skips** with an explicit reason (does not fake a pass). CI now starts a Redis service and sets `TEST_REDIS_URL`, so these tests run on GitHub Actions instead of skipping.

**Files:**
- [`tests/test_rate_limit.py`](tests/test_rate_limit.py) — `real_redis` fixture, two `test_real_redis_*` tests
- [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — Redis 7 service + `TEST_REDIS_URL=redis://localhost:6379/0`

**Verified:**
- `docker compose up -d redis` → `redis.asyncio` `PING` → `True`
- `pytest tests/test_rate_limit.py -v` — **8 passed**, including both real-Redis tests

**Note:** `fakeredis[lua]` was not added; a live Redis interpreter is a stronger check. If Redis is down locally, skip is expected. Re-run:

```text
docker compose up -d redis
pytest tests/test_rate_limit.py -k real_redis -v
```

A human should confirm the next GitHub Actions **test** job logs `test_real_redis_lua_script_loads PASSED` (not SKIPPED). That cannot be confirmed from this machine.

---

## 2. `pip-audit --severity-level` in CI

**Status:** Fixed.

**Actual current (pre-fix) behavior:** The flag is **not** silently ignored. `pip-audit` 2.9.0 (and current 2.10.x) has **no** `--severity-level` option ([pypa/pip-audit#654](https://github.com/pypa/pip-audit/issues/654) is still the severity-filtering request). argparse treats `high` as `project_path`, which cannot be combined with `-r`, and the process exits **2**.

The CI job had **no** `continue-on-error` and **no** `|| true`. Unpinned `pip install pip-audit` would install latest; that latest also lacks the flag. So this step was **failing the workflow** (or would fail on the next run), not reporting vulnerabilities.

`pip-audit --help` locally (`2.9.0`): no `severity` option.

**Change (chosen option: report all severities, fail on any finding):**
- Pin CI to `pip-audit==2.9.0` (same as [`requirements-dev.txt`](requirements-dev.txt)).
- Command: `pip-audit -r requirements.txt --progress-spinner off` (default: non-zero exit if any advisory is found).
- Left `typecheck` `continue-on-error: true` — that job is labeled advisory mypy, unrelated to pip-audit.

**Files:**
- [`.github/workflows/ci.yml`](.github/workflows/ci.yml) — `pip-audit` job (~79–93)

**Verified:**
- `pip-audit --help` — no `--severity-level`
- `pip-audit -r requirements.txt --progress-spinner off` — **No known vulnerabilities found**, exit 0
- YAML inspected by hand (PyYAML not installed). No `continue-on-error` on the pip-audit job.

**Note:** GitHub Actions was not run here. On the next push/PR, confirm the **pip-audit** job is green and the step name is `Run pip-audit (fail on any finding)`.

---

## 3. The 4 skipped tests

**Status:** Explained; not stale. Skip reason made explicit. All four **pass** when `TEST_DATABASE_URL` is set.

`pytest -v -rs` without Postgres env (earlier this session):

| Test | File:line | Reason | Classification |
|------|-----------|--------|----------------|
| `test_upsert_movie_insert_and_overwrite` | [`tests/test_crud_upsert.py`](tests/test_crud_upsert.py):38 | `TEST_DATABASE_URL not set` | Environment-gated (live Postgres) |
| `test_upsert_user_activity_increments` | same file:65 | same | same |
| `test_concurrent_movie_upserts` | same file:75 | same | same |
| `test_list_movies_window_count` | same file:98 | same | same |

Skip is in the `session` fixture (not a bare `@pytest.mark.skip`). CI already set `TEST_DATABASE_URL` via the Postgres service, so these **already run in CI** — not a CI gap.

**Change:** skip message now states they are Postgres integration tests and that CI sets the URL. Not un-skipped unconditionally (they need a real DB).

**Verified with Docker Postgres:**

```text
docker compose up -d db
TEST_DATABASE_URL=postgresql+asyncpg://postgres:postgres@localhost:5432/tgbot
pytest tests/test_crud_upsert.py -v
```

**4 passed.** Full suite with both compose services: **47 passed, 0 skipped**.

Without `TEST_DATABASE_URL` locally, the four still skip by design.

---

## Final verification

| Check | Result |
|-------|--------|
| `pytest -v -rs` (compose Redis + Postgres, `TEST_DATABASE_URL` + `TEST_REDIS_URL`) | **47 passed**, 0 skipped |
| `ruff check bot tests` | All checks passed |
| Real Redis Lua EVAL | `test_real_redis_*` **PASSED** |
| CRUD integration | 4 tests **PASSED** when `TEST_DATABASE_URL` is set |
| `pip-audit -r requirements.txt --progress-spinner off` | No known vulnerabilities found |

**Still needs a human / next CI run:**
1. Confirm GitHub Actions **test** job runs `test_real_redis_*` as PASSED (Redis service healthy).
2. Confirm GitHub Actions **pip-audit** job succeeds with the new command (no argparse error).
3. Local default (`pytest` with no `TEST_DATABASE_URL`) will still skip the four CRUD tests; that is expected.
