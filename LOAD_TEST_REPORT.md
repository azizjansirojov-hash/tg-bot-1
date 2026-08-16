# Load Test Report — Telegram Movie-Code Bot

**Date:** 2026-08-12
**Target:** quantify how this single-instance webhook bot behaves under 500 → 100,000 near-simultaneous local webhook requests, **without** calling `api.telegram.org`.
**Verdict (short):** this current single-process setup does **not** handle 10,000 / 20,000 / 30,000+ *truly simultaneous* webhook deliveries without slowing down or breaking. It *can* absorb a Telegram-realistic inbound rate (~30 updates/sec, and even several hundred webhook POSTs/sec) for a large *user base over time*. Those two statements are not the same product claim.

---

## Methodology

### What was tested

Local Docker Postgres 16 + Redis 7 (`docker compose up -d db redis`), plus a **single** Python bot process serving `POST /webhook` on `127.0.0.1:8080`. Outbound Telegram Bot API calls were stubbed. Load was applied to this application's handlers, SQLAlchemy/asyncpg pool, Redis-backed FSM, and Redis-backed rate limiter.

### Why the real Telegram API was never called

Telegram ToS and global rate limits make a 50k-request storm against `api.telegram.org` both unsafe and scientifically useless: Telegram itself caps bots at roughly **30 messages/sec across all chats** and **1 message/sec per chat**. Hitting the live API would measure Telegram's throttle, not this codebase. All `Bot.set_webhook` / `Bot.delete_webhook` / `safe_answer` / `safe_send_video` / rate-limit notify paths were replaced in a **temporary, process-local runner** (`scripts/run_loadtest_bot.py`, deleted after the run). Production modules under `bot/` were not permanently patched.

### What was stubbed (temporary runner only)

| Call | Production location | Load-test replacement |
|------|---------------------|------------------------|
| `bot.set_webhook` / `bot.delete_webhook` | `bot/__main__.py` `run_webhook` | class-level `Bot.set_webhook` / `Bot.delete_webhook` → async no-op returning `True` after 50–150 ms jitter |
| `safe_answer` | `bot/services/telegram.py`; imported by `bot/handlers/user.py`, `bot/handlers/admin.py` | sleep 50–150 ms, return `None` |
| `safe_send_video` | `bot/services/telegram.py`; imported by `bot/handlers/user.py` | sleep 50–150 ms, return a dummy success object (so the handler does **not** take the `VIDEO_UNAVAILABLE` fallback) |
| `RateLimitMiddleware._notify_limited` | `bot/middlewares/rate_limit.py` (calls `message.answer` directly) | sleep 50–150 ms, return |
| `bot.session.close` | aiogram session teardown | no-op so shutdown does not open a real HTTP session |

Stub latency (50–150 ms) approximates a successful Telegram HTTP round-trip so the event loop still holds in-flight tasks the way production would.

Safety check: bot log line 1 is `LOAD TEST MODE: Telegram outbound API is stubbed.` Boot then logged `Webhook set to https://example.com/webhook` **after** the stubbed `set_webhook` (no DNS/network call to Telegram). Zero requests were issued to `api.telegram.org`.

### Runtime configuration used for the test

- `BOT_MODE=webhook`, `WEBHOOK_PATH=/webhook`, `PORT=8080`
- `USE_REDIS=true`, `REDIS_URL=redis://127.0.0.1:6379/0` (production-scale path; **not** MemoryStorage)
- `DB_POOL_SIZE=20`, `DB_MAX_OVERFLOW=40` (raised from code defaults `5` / `10` in `bot/config.py` so pool exhaustion would be visible if it happened; it did **not** become the first limiter — see Results)
- `RATE_LIMIT_MAX_REQUESTS=5` / 60s (code lookups, non-admins)
- `RATE_LIMIT_GLOBAL_MAX_REQUESTS=1000` / 60s (raised from default `60` only so a 50-hit single-user burst probe could still distinguish code-limit vs global-limit; per-user global of 60 would **not** have blocked the 1-request-per-distinct-user main mix)
- Seed: **800** movie rows in `movies` (codes `100001`–`100800`)
- Secret header: `X-Telegram-Bot-Api-Secret-Token` set to the test `WEBHOOK_SECRET` so aiogram `SimpleRequestHandler` did not 403 the traffic before handlers

### Load generator

**Custom asyncio + aiohttp script** (`scripts/load_test_campaign.py`, deleted after the run).

k6 and Locust were **not** used: this environment already had `aiohttp` from the project dependencies, and a custom generator could (a) build valid Telegram Update JSON, (b) attach the secret header, (c) sample Postgres/Redis/process metrics between stages, and (d) avoid installing extra tooling. Each stage fired **N concurrent** `POST /webhook` coroutines in one `asyncio.gather` (a near-simultaneous burst, not a ramped arrival process). Client timeout was 15 s.

**Measurement caveat:** the load generator and the bot ran on the **same Windows host**. Stages ≥ 20,000 therefore include client-side / OS socket exhaustion, not only bot-server capacity. The 500 and 5,000 stages are the cleanest application-capacity measurements (0 HTTP/client errors).

### Synthetic traffic mix (per stage)

| Share | Payload |
|-------|---------|
| ~70% | numeric movie-code messages; 90% existing codes, 10% non-existent |
| ~15% | `/start` |
| ~10% | admin commands (`/stats`, `/list_codes`, `/auditlog`, `/delete_code 123`) from configured test `ADMIN_IDS` `123456789,987654321` |
| ~5% | malformed / edge (empty, whitespace, non-numeric, 5000-char text) |

Each of the N requests in a stage used a **distinct** `from.id` / `chat.id` (base `1000000000 + i`), except the 10% admin slice which used the two configured admin IDs (realistic admin proportion, not 50k admin users). After each stage, a **50-request burst from a single fake user** (`777777777`, code `123456`) probed whether the Redis rate limiter still blocked abuse under load.

Stages: 500 → 5,000 → 20,000 → 50,000 → 100,000, with a 2 s cooldown between stages.

---

## Results table

All latencies are webhook HTTP round-trip time as seen by the load generator (includes stub 50–150 ms). `attempted rps` = total / wall time of the gather; `achieved rps` = 2xx / wall time.

| Stage | N | 2xx | 4xx | 5xx | timeout | client exceptions | error % | p50 (ms) | p95 (ms) | p99 (ms) | max (ms) | attempted rps | achieved rps | DB conns (active / total) | Redis clients | Redis memory | Redis ops/s | Bot CPU % | Bot RSS |
|-------|---|-----|-----|-----|---------|-------------------|---------|----------|----------|----------|----------|---------------|--------------|---------------------------|---------------|--------------|-------------|-----------|---------|
| 1 baseline | 500 | 500 | 0 | 0 | 0 | 0 | **0.0** | 344 | 368 | 370 | 371 | 969 | 969 | 1 / 7 | 363 | 7.87M | 20 | 103 | 285 MB |
| 2 moderate | 5,000 | 5,000 | 0 | 0 | 0 | 0 | **0.0** | **4,836** | 5,617 | 5,648 | 5,679 | 648 | 648 | 1 / 26 | 2,813 | 29.06M | 981 | 99.9 | 759 MB |
| 3 high | 20,000 | 580 | 0 | 0 | 0 | 19,420 | **97.1** | 10,845 | 11,519 | 11,531 | 11,535 | 1,648 | **48** | 1 / 26 | 4,976 | 25.45M | 1,277 | 100 | 771 MB |
| 4 target | 50,000 | 3,743 | 0 | 0 | 361 | 45,896 | **92.5** | 15,063 | 15,460 | 15,484 | 15,493 | 2,922 | 219 | 1 / 26 | 4,976 | 77.81M | 2,289 | 96.8 | 1,041 MB |
| 5 stress | 100,000 | 3 | 0 | 0 | 411 | 99,586 | **99.997** | 7,088 | 7,822 | 7,887 | 7,904 | 3,734 | **0.11** | 1 / 26 | 4,976 | 14.29M | 20 | 0.0 | 776 MB |

Notes on the table:

- **No HTTP 4xx/5xx** at any stage. Requests that reached aiohttp completed with 200. Failures at ≥ 20k are **client exceptions / timeouts** (connection not accepted or not completed within 15 s), not application 500s.
- Postgres `pg_stat_activity` never showed connection saturation. Peak `total` connections observed during stages was **26** against a configured cap of `pool_size + max_overflow = 60`. Default production cap is `5 + 10 = 15` (`bot/config.py`).
- Redis `maxclients=10000`; peak connected clients **4,976** (plateau from stage 3 onward). `rejected_connections=0` in the post-run `INFO stats`. Redis processed **198,602** commands over the campaign; `evicted_keys=0`.
- Bot process stayed alive through 100k (RSS ~776–1,041 MB). It did **not** crash; at 100k it was effectively no longer completing work (CPU 0% snapshot after the storm, 3 successes).
- aiohttp access log recorded `POST /webhook HTTP/1.1" 200` throughout; malformed payloads did not crash the process.

### Rate limiter under load

- After stage 1, a 50-hit burst from user `777777777` produced:
  `Rate-limit abuse signal user_id=777777777 block_count=281 window_seconds=300`
  (`RATE_LIMIT_ABUSE_THRESHOLD=10`). The limiter **did not fail open** at 500 concurrent: a single-user burst was blocked and the abuse WARNING fired.
- Stages 2–5 recorded `limiter_burst_block_signals=0` because the post-stage burst probe itself mostly failed to complete (same connection collapse as the main mix). That is **not** evidence the limiter failed closed for everyone — distinct-user requests that *did* get a 200 were processed (5,000/5,000 at stage 2). It **is** evidence that under a 20k+ connection storm the limiter cannot be observed via HTTP because the server stops accepting sockets first.
- Redis rate-limit keys use TTL (`window + 1`); post-run `expired_keys=22017` shows windows were reclaimed rather than growing without bound.

---

## Breaking point

**First degradation (latency, not errors): 5,000 concurrent in-flight webhook POSTs.**

Evidence:

- Stage 1: 0% errors, p50 **344 ms** (already ~2× a single-request budget of stub 50–150 ms + Redis + one indexed `movies` lookup).
- Stage 2: still 0% errors, but p50 **4.84 s** (~14× stage 1) and p99 **5.65 s**. Throughput fell from **969 rps to 648 rps**. Bot CPU **~100%**. RSS jumped **285 MB → 759 MB**. Redis clients **363 → 2,813**.

**Hard failure (most requests never complete): 20,000 concurrent.**

Evidence:

- 97.1% client exceptions, only 580/20,000 HTTP 200s, achieved **48 rps**.
- Redis client count **capped at 4,976** and stayed there through 50k and 100k — the process was no longer opening useful new Redis work; it was saturated.
- DB connections stuck at **26** from stage 2 onward — the pool was **not** exhausted (`DB_POOL_SIZE=20` + overflow unused relative to 60). Postgres was waiting on the app, not the other way around.
- Stage 5 (100k) achieved **0.11 rps** (3 successes). The bot process was still up (RSS 776 MB) but not serving the storm.

### What actually limited the system (ranked)

1. **Single-process asyncio + one CPU core (GIL).** `bot/__main__.py` starts one `web.TCPSite` in one process. CPU was already **103% at 500 concurrent** and stayed pegged. Every update does JSON parse → Redis pipeline (rate limit) → DB session → stub sleep. There is no worker pool and no horizontal replica in `docker-compose.yml`.

2. **aiohttp listen backlog default (128)** on `web.TCPSite(runner, host="0.0.0.0", port=settings.port)` in `bot/__main__.py`. A 20,000-connection simultaneous `gather` overflows a 128-deep accept queue; the OS drops/refuses the rest. That matches “0 HTTP 5xx, huge client exception counts.”

3. **Unbounded Redis client pool.** `Redis.from_url(settings.redis_url)` in `bot/__main__.py` `_build_fsm_storage` / `_build_rate_limit_middleware` uses redis-py’s default pool (`max_connections` effectively unlimited). Under concurrency this grew to **~5,000 Redis connections** from one bot process (Redis `maxclients=10000`). That is file-descriptor and RAM pressure (RSS 759 MB at 5k, 1,041 MB at 50k) and is a production foot-gun even before Redis itself rejects clients.

4. **Per-request INFO access logging.** The bot log grew to millions of characters of `aiohttp.access` lines. Logging every webhook POST on the event loop adds real overhead at hundreds of rps.

5. **Not the first limiter: Postgres pool.** Peak 26 connections vs test cap 60 and vs default cap 15. If the event loop were scaled out (many replicas) *without* shrinking `DB_POOL_*` per process, pool exhaustion would become the next wall (`pool_size + max_overflow` per replica × replica count — already flagged in `SECURITY_HARDENING_REPORT.md`).

6. **Not measured as a limiter: Redis command latency.** Instantaneous ops peaked at 2,289/s with 0 rejected connections. Redis was busy but not the breaking component.

---

## Plain-language answer

**Question:** Can this bot currently handle 10,000 / 20,000 / 30,000+ simultaneous users without slowing down or breaking?

**Answer, for this codebase as it exists today (one Python process, webhook mode, Redis on, current architecture):**

| Claim | Result |
|-------|--------|
| **10,000 truly simultaneous webhook POSTs** | **No.** At 5,000 concurrent, p50 is already **4.8 seconds** (severe slowdown, 0 errors). At 20,000, **97% of requests never complete**. 10,000 sits in the zone where latency is already unacceptable and connection refusal is starting. |
| **20,000 truly simultaneous** | **No.** Measured: 97.1% failure, 48 rps achieved vs 1,648 attempted. |
| **30,000+ truly simultaneous** | **No.** 50,000: 92.5% failure. 100,000: 99.997% failure. The process did not crash; it stopped being able to accept/finish work. |
| **10,000–50,000 users over time, Telegram-realistic arrival** | **Yes, with caveats.** Telegram will not deliver 10k updates in one instant. At ~30 inbound updates/sec the bot’s measured headroom at stage 1 (~970 rps webhook completions, p50 344 ms under a 500-wide burst) is **tens of times** Telegram’s own send/receive ceiling. A large *registered user base* is not the same as a large *in-flight request count*. |

**“Currently” means:** one bot process, one event loop, `USE_REDIS=true`, Docker Postgres+Redis on the same machine as the load generator, test pool 20+40 (defaults 5+10 would be *tighter* if the app were ever able to drive more DB concurrency). It does **not** mean a multi-replica production deployment, a queue in front of `send_video`, or a tuned `TCPSite(backlog=...)`.

**What “degrade” looked like:** first slower (seconds instead of hundreds of ms, CPU pegged), then errors that are connection failures rather than handler crashes or HTTP 500s. Malformed payloads mixed into the storm did not take the process down.

---

## Telegram API ceiling context (independent of this app)

This load test answers “how fast can *our* webhook + DB + Redis path ingest updates if Telegram I/O is a 50–150 ms stub.” It does **not** answer “can we *deliver* 50,000 videos at once.”

Telegram’s documented practical ceilings for bots are on the order of:

- ~**30 messages/second** across all chats
- ~**1 message/second** to any single chat
- additional flood-wait (`retry_after`) when exceeded

So “50,000 simultaneous users” as a **business** number almost always means 50,000 people who *might* send a code this week/hour, with a much smaller peak of *in-flight* updates. Even if this bot’s HTTP server were infinitely fast, **outbound `send_video` would still be paced at ~30/sec**. 50,000 successful deliveries would take on the order of **50,000 / 30 ≈ 28 minutes** of drain time, plus per-chat 1/sec. Bursting 50,000 `send_video` calls without a queue would produce `TelegramRetryAfter` storms (the production code already sleeps and retries once in `bot/services/telegram.py`).

**Product implication:** do not treat “the webhook returned 200 to 50k POSTs” as “50k users got their movie.” Launch capacity is bounded by (1) this app’s ingest/queue, (2) Telegram’s send ceiling, (3) per-user rate limits (5 codes/minute for non-admins). For a movie-code bot, a realistic launch question is “can we keep p95 webhook ingest under ~1 s at a few hundred rps and drain sends at 30/s without losing updates,” not “can we complete 50,000 send_video calls in one second.”

---

## Prioritized recommendations

Ranked by **(a) headroom vs the measured bottleneck** and **(b) cheap/quick to implement**. Each item is tied to evidence above.

1. **Add an outbound send queue (highest product value, medium effort).**  
   Evidence: even at a healthy ingest rate (~650–970 rps) Telegram will only accept ~30 sends/sec. `safe_send_video` today does inline I/O (and flood-wait sleep) on the handler task. A Redis/Postgres queue that workers drain at Telegram-safe rates absorbs bursts, avoids retry storms, and matches how “50k users” actually arrive. Headroom: turns a burst into a backlog instead of user-visible failure. Cost: one worker + table/stream; does not require rewriting handlers’ lookup path.

2. **Cap the Redis connection pool (cheap, high risk-reduction).**  
   Evidence: one process opened **~5,000** Redis clients (`Redis.from_url` in `bot/__main__.py` with default unlimited pool). Set `max_connections` to something like 20–50 per process, shared by FSM + rate limiter. Headroom: prevents FD/RAM blow-up under burst; RSS was already 759 MB at 5k concurrent. Cost: a few lines.

3. **Raise `TCPSite` backlog and run behind a reverse proxy (cheap).**  
   Evidence: default backlog **128** vs 20k simultaneous connects; failures were accept/connect errors, not 5xx. Set an explicit `backlog` (e.g. 2048–4096) and put nginx/caddy in front with a bounded proxy queue. Headroom: fewer refused connections during short bursts. Cost: one constructor argument + compose/proxy config. Does **not** fix the 4.8 s p50 at 5k — that is CPU/event-loop.

4. **Horizontal replicas now that Redis FSM + rate limit exist (medium effort, large ingest headroom).**  
   Evidence: CPU 100% on one process at 500–5,000 concurrent; `SECURITY_HARDENING_REPORT.md` already states Redis makes multi-replica rate-limit/FSM safe. Run N webhook workers behind a load balancer; **only one** process should `set_webhook`. Shrink `DB_POOL_*` so `N × (pool_size + max_overflow)` stays under Postgres `max_connections`. Headroom: roughly linear ingest until DB or Redis becomes the wall. Cost: process supervisor / extra compose service; webhook registration discipline.

5. **Do not raise `DB_POOL_SIZE` as the first knob (cheap but low payoff *until* replicas exist).**  
   Evidence: pool used **26** connections with 20+40 configured; defaults 5+10 were not the breaking point. After replicas, *then* size pools using the formula in `SECURITY_HARDENING_REPORT.md`. Blindly setting `DB_POOL_SIZE=50` on one process buys almost nothing here.

6. **Turn down access logs in production (cheap).**  
   Evidence: multi-MB `aiohttp.access` INFO log during the run. Use WARNING+ for access, or sample. Headroom: some event-loop time back at hundreds of rps.

7. **Keep `USE_REDIS=true` for any production/multi-user deploy (already done in this test).**  
   Evidence: in-memory limiter is capped at `RATE_LIMIT_MAX_TRACKED_USERS=10000` and is replica-unsafe. This test used Redis; do not load-test or launch on MemoryStorage at this scale.

8. **Optional later: Postgres read replica / extra indexes.**  
   Evidence: `get_movie_by_code` is a unique-index lookup; `upsert_user_activity` is the write amplification on the hot path. A read replica is **not** justified by this test (DB was idle relative to the app). Revisit only after replicas push `pg_stat_activity` to the pool cap.

---

## Cleanup confirmation

Temporary load-test scaffolding was **not** merged into production modules:

- No lasting edits to `bot/__main__.py`, `bot/services/telegram.py`, `bot/handlers/*`, or `bot/config.py`.
- Temporary files created for the campaign and **removed after this report**:
  - `scripts/run_loadtest_bot.py`
  - `scripts/load_test_campaign.py`
  - `load_test_results.json`
  - `load_test_bot.log`
  - `.env.loadtest` (if present)
- `.env` was restored to its pre-test contents by the campaign runner’s `finally` block.
- Docker: `db` + `redis` were used for the test; stack torn down with `docker compose down` after verification commands.
- Post-cleanup verification:
  - `pytest -v` — **27 passed, 4 skipped** (skips are the existing Postgres-integration tests that require `TEST_DATABASE_URL`; same as pre-test).
  - `ruff check .` — **All checks passed.**

This report file (`LOAD_TEST_REPORT.md`) is the only intended lasting artifact of the campaign.
