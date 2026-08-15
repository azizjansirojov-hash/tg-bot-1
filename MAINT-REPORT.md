# Maintenance report (2026-08-15)

## Conclusions

(a) Prior named audit/feature docs (`FIXES.md`, `FEATURES.md`, `DEBUG-REPORT.md` and follow-ups) were never in git; the large uncommitted working tree is now committed as `ee33dc8` and pushed to `origin/main`.

(b) The local environment now matches the lockfile at `aiohttp==3.14.3`, and `pip-audit -r requirements.txt` reported no known vulnerabilities.

(c) A non-admin who forwards a storage-channel video now receives `ADMIN_ONLY` in their language; an ordinary (non-forward) video does not.

---

## ITEM 1 — Git history / commit hygiene

**Status:** Done (investigation exact; working tree persisted in this session’s commit).

**Finding:**

- Workspace at investigation time had only `README.md` among `*.md` files. `FIXES.md`, `FIXES-FOLLOWUP.md`, `FIXES-MINOR.md`, `FEATURES.md`, `FEATURES-FOLLOWUP.md`, `DEBUG-REPORT.md`, and `DEBUG-STEPTHROUGH-REPORT.md` were **not on disk**.
- `git log --all --oneline --` those paths was **empty**. They were never committed on any branch.
- Only branch: `main` at `bc3fc28`, matching `origin/main`. Not “on another branch” and not “committed locally but unpushed.”
- `.gitignore` does **not** exclude `*.md`. Silent ignore was not the cause.
- Those named files were never durable in this repo (transient prior-session working directory, or a different clone). Claims in them are **not** backed by git objects.
- Different reports **were** in history at `bc3fc28` / `origin/main`: `CLEANUP_REPORT.md`, `DEBUG_TEST_REPORT.md`, `DOCKER_STACK_TEST_REPORT.md`, `FIX_REPORT.md`, `GITHUB_PUSH_REPORT.md`, `SECURITY_HARDENING_REPORT.md`, `UPSERT_FIX_REPORT.md`. Those were **deleted in the working tree** (unstaged) as part of a later uncommitted pass.
- Real hygiene problem: `main` was up to date with `origin/main`, but the working tree held a large **uncommitted** product pass (i18n, broadcast, aiohttp lockfile bump 3.13.3 → 3.14.3, CI, tests, etc.). Same class of session-loss as the missing FIXES docs.
- HEAD lockfile still had `aiohttp==3.13.3`; only the working tree had `3.14.3`.

**Change:**

- Did not invent `FIXES.md` / `FEATURES.md` content that was never in the repo.
- Included working-tree deletions of the older `*_REPORT.md` files (still recoverable from `bc3fc28`).
- Staged project files only (not `.venv/`, `.pytest_cache/`, `.ruff_cache/`).
- Added this `MAINT-REPORT.md`.
- Recommended **not** adding a CI gate that fails if generated report docs are missing: filenames drift and those files are not CI artifacts. Better: commit and push at the end of each session.
- README: after `git pull`, reinstall from the hashed lockfile (see item 2).

**Files:** `MAINT-REPORT.md`, `README.md`, plus the previously uncommitted product/test/CI/lockfile tree (see git commit).

**Verified:** `git log --all --oneline -- FIXES.md FEATURES.md DEBUG-REPORT.md` empty; `.gitignore` has no `*.md` rule; `git status` / `git log --oneline -20` recorded at investigation.

**Push:** Remote `https://github.com/azizjansirojov-hash/tg-bot-1.git`. Commit `ee33dc8` was pushed: `bc3fc28..ee33dc8  main -> main`. `git status -sb` after push: `## main...origin/main`.

---

## ITEM 2 — aiohttp version mismatch

**Status:** Fixed (environment + lockfile alignment; assertion unchanged).

**Finding:**

| Source | Version |
|--------|---------|
| `.venv` before this session | `aiohttp==3.13.3` |
| Working-tree `requirements.in` / `requirements.txt` | `aiohttp==3.14.3` |
| `HEAD` / `origin/main` lockfile | `aiohttp==3.13.3` |
| `requirements-dev.txt` | no aiohttp pin |

Root cause: lockfile was bumped in the working tree but never committed, and the venv was never reinstalled. Not a second pin. CI already runs `pip install --require-hashes -r requirements.txt`, so CI would match 3.14.3 once the lockfile is committed. Local drift was the gap. `aiohttp==3.13.3` was the advisory-flagged version from the earlier audit.

**Change:**

- `.venv\Scripts\python.exe -m pip install --require-hashes -r requirements.txt` (installed `aiohttp==3.14.3`, also pulled `async-timeout==5.0.1`).
- Installed `requirements-dev.txt` so `pip-audit` is available.
- Did **not** loosen `tests/test_startup.py` (`assert major_minor == "3.14"`).
- README install steps now use `--require-hashes` and note reinstall after `git pull`.

**Files:** local `.venv` (not committed); `README.md`; `requirements.in` / `requirements.txt` (already updated in WD, now committed).

**Verified:**

- `pip show aiohttp` → `3.14.3`
- `pip-audit -r requirements.txt --progress-spinner off` → `No known vulnerabilities found`
- `tests/test_startup.py::test_webhook_without_redis_logs_warning` PASSED

**Drift risk:** A developer who pulls the lockfile bump but does not reinstall the venv will fail the aiohttp assertion locally. CI already reinstalls from hashes, so CI will not silently drift. Recommendation: after every `git pull` that touches `requirements.txt`, re-run `pip install --require-hashes -r requirements.txt`. A CI job that “fails if report markdown is missing” is not warranted; a lockfile reinstall step already exists in CI.

---

## ITEM 3 — Non-admin storage-channel video reply

**Status:** Fixed.

**Finding:** Admin router applies `IsAdmin()` globally, so `admin_forward_video` never runs for non-admins. User router only denied slash commands (`admin_commands_denied`). A non-admin storage-channel forward got no FSM (correct) and **no reply** (inconsistent with `/list_codes` etc.).

**Change:** User-router handler `admin_storage_forward_denied`: private video; skip if admin; reply `texts.ADMIN_ONLY` only when `extract_storage_forward` matches the storage channel (same predicate as the admin add-movie start). Ordinary videos (not a storage-channel forward) still get no denial reply.

**Files:** `bot/handlers/user.py`, `tests/test_non_admin_video.py`

**Verified:**

- `test_non_admin_storage_forward_gets_admin_only` — English `ADMIN_ONLY`, FSM state `None`
- `test_non_admin_ordinary_video_is_not_admin_only` — no `ADMIN_ONLY`, FSM state `None`

---

## Final verification

| Check | Result |
|-------|--------|
| `pytest -v` | 84 passed, 7 skipped (DB-backed CRUD; no `TEST_DATABASE_URL`) |
| `ruff check bot tests` | All checks passed |
| `mypy bot` | Success: no issues found in 35 source files |
| `pip show aiohttp` | 3.14.3 |
| `pip-audit -r requirements.txt` | No known vulnerabilities found |
