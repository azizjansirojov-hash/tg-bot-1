# GitHub sync report (2026-08-15)

Verification from live git commands after `git fetch --all`. Prior `MAINT-REPORT.md` was not trusted as source of truth.

## ITEM 1 — Remote and branch state

**Status:** Local `main` was **ahead 1** of `origin/main` at the start of this check; not diverged. Push is Item 5.

**Finding:**

- `git remote -v`: `origin` fetch and push are exactly `https://github.com/azizjansirojov-hash/tg-bot-1.git`.
- `git fetch --all`: completed; no new remote commits.
- `git status -sb` (pre-push): `## main...origin/main [ahead 1]`
- `git rev-list --left-right --count origin/main...HEAD`: `0	1` (origin has 0 unique; local has 1 unique).
- `origin/main` tip: `ac2c366` Record that the hygiene commit was pushed to origin/main.
- Local `HEAD` tip (pre this report commit): `b62aeb5` Restore report markdown files accidentally deleted in ee33dc8.
- `git log --oneline -10` (local): `b62aeb5`, `ac2c366`, `ee33dc8`, `bc3fc28`, `453b4a1`, `966c972`, `f83b482`, `af3e707`, `82bfb52`, `094527e`.
- Branches: local `main` only; remotes `origin/HEAD -> origin/main` and `origin/main`. No extra feature branches.

**Change:** None in this item (no divergence to resolve). Ahead-1 is the restore commit `b62aeb5`, which must be pushed in Item 5.

**Verified:** `git fetch --all`, `git status -sb`, `git branch -a`, `git rev-list --left-right --count origin/main...HEAD`.

---

## ITEM 2 — Full working tree audit

**Status:** Clean working tree except this report file (added and committed in this pass). `.gitignore` already covers venv/caches/`.env`.

**Finding:**

- `git status --porcelain=v1` after fetch: **empty** (no modified, deleted, or untracked project files).
- `.gitignore` already lists `.env`, `.env.local`, `*.pem`, `.venv/`, `venv/`, `ENV/`, `__pycache__/`, `.pytest_cache/`, `.mypy_cache/`, `.ruff_cache/`, `.coverage`, `htmlcov/`, `*.log`.
- No missing ignore entries identified.

**Change:** Added `GITHUB-SYNC-REPORT.md` (this file) as the only new project artifact. No other files to stage.

**Verified:** `git status --porcelain=v1` empty before this file; `.gitignore` inspected.

---

## ITEM 3 — Secret leak check

**Status:** No secrets in git history or tracked files. Local `.env` (gitignored) contains a live-looking bot token and was **not** staged.

**Finding:**

1. `.env` is in `.gitignore` (`git check-ignore -v .env` → `.gitignore:2:.env`).
2. `git log --all --full-history -- .env` is **empty**. `.env` has never been committed. Not CRITICAL for history.
3. `git ls-files .env` empty; `.env.example` is tracked (placeholders only).
4. Tracked Telegram-token-shaped strings are placeholders (`1234567890:AAHxxxx…`) in `.env.example`, `tests/conftest.py`, `tests/test_config.py`, `tests/test_startup.py`, `tests/test_admin_fsm.py`, `tests/test_non_admin_video.py`.
5. Tracked DB URLs use local/dev defaults (`postgres:postgres@localhost` or `u:p@localhost`) in CI, compose, tests, `.env.example`, README. Not production hosts.
6. Untracked `.env` line 2 matches a real Telegram bot-token pattern (not a placeholder). **Value is not copied into this report.** File remains untracked.
7. `.github/workflows/ci.yml` has no `${{ secrets.* }}` (CI does not need production secrets). `POSTGRES_PASSWORD: postgres` is the GitHub Actions **service container** default for ephemeral test Postgres, not a repo secret. No literal `BOT_TOKEN` or cloud password in YAML.
8. `requirements.txt` is a hashed lockfile of package versions, not credentials.

**Change:** Did not commit `.env`. Did not rewrite history.

**Verified:** `git log --all --full-history -- .env`; `git grep` on tracked files; `git check-ignore -v .env`; workflow YAML read.

**Recommendation:** Keep `.env` untracked. If this machine or chat logs might have exposed the local token, rotate `BOT_TOKEN` with BotFather (history rewrite is not required — the token was never in git).

---

## ITEM 4 — Document trail

Checked: on disk, `git log --all --oneline -- <file>`, and `git cat-file -e origin/main:<file>` (pre-push).

| File | Disk | Committed (any ref) | On `origin/main` (pre-push) | Verdict |
|------|------|---------------------|-----------------------------|---------|
| AUDIT.md | no | no | no | **Genuinely missing** — never in this repo; not reconstructed |
| FIXES.md | no | no | no | **Genuinely missing** |
| FIXES-FOLLOWUP.md | no | no | no | **Genuinely missing** |
| FIXES-MINOR.md | no | no | no | **Genuinely missing** |
| FEATURES.md | no | no | no | **Genuinely missing** |
| FEATURES-FOLLOWUP.md | no | no | no | **Genuinely missing** |
| DEBUG-REPORT.md | no | no | no | **Genuinely missing** |
| DEBUG-STEPTHROUGH-REPORT.md | no | no | no | **Genuinely missing** |
| MAINT-REPORT.md | yes | `ac2c366` | yes | **Present-and-pushed** |
| CLEANUP_REPORT.md | yes | `b62aeb5` | no (pre-push) | **Present-but-not-pushed** — fix: push `b62aeb5` |
| DEBUG_TEST_REPORT.md | yes | `b62aeb5` | no | **Present-but-not-pushed** |
| DOCKER_STACK_TEST_REPORT.md | yes | `b62aeb5` | no | **Present-but-not-pushed** |
| FIX_REPORT.md | yes | `b62aeb5` | no | **Present-but-not-pushed** |
| GITHUB_PUSH_REPORT.md | yes | `b62aeb5` | no | **Present-but-not-pushed** |
| SECURITY_HARDENING_REPORT.md | yes | `b62aeb5` | no | **Present-but-not-pushed** |
| UPSERT_FIX_REPORT.md | yes | `b62aeb5` | no | **Present-but-not-pushed** |

The FIXES/FEATURES/DEBUG/AUDIT family cannot be reconstructed here; original content is gone.

**Change:** None of the missing files were invented. Restored reports are already in local `b62aeb5` awaiting push.

**Verified:** disk glob, `git log --all --oneline -- <file>`, `git ls-tree origin/main`, `git ls-tree HEAD`.

---

## ITEM 5 — Push and final confirmation

**Status:** Filled after push (see below).

**Finding (pre-push):** Local ahead by `b62aeb5` plus this report commit.

**Change:** Commit this report; `git push origin main`; `git fetch`; confirm `## main...origin/main` with no ahead/behind; GitHub trees API cross-check; `pytest -v`, `ruff check bot tests`, `mypy bot`.

**Verified:** See closing block after those commands.

---

## Closing verification (post-push)

_Placeholder — updated in the same working pass after push and checks._
