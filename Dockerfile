# syntax=docker/dockerfile:1

FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
# Hash-locked install verifies every wheel/sdist against requirements.txt hashes.
RUN pip install --no-cache-dir --require-hashes --prefix=/install -r requirements.txt


FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    BOT_MODE=webhook \
    PORT=8080

WORKDIR /app

# Non-root runtime user — never run the bot as root in production.
RUN useradd --create-home --uid 1000 appuser

COPY --from=builder /install /usr/local
COPY alembic.ini .
COPY alembic ./alembic
COPY bot ./bot

USER appuser

EXPOSE 8080

# Image default is BOT_MODE=webhook (HEALTHCHECK hits /healthz).
# For polling-only deployments, either leave BOT_MODE=polling (check exits 0)
# or disable the healthcheck in your orchestrator.
HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import os,sys,urllib.request; m=os.environ.get('BOT_MODE','webhook'); p=os.environ.get('PORT','8080'); sys.exit(0) if m!='webhook' else urllib.request.urlopen('http://127.0.0.1:%s/healthz'%p,timeout=4)"

# Run migrations then start the bot (webhook or polling via BOT_MODE).
CMD ["sh", "-c", "alembic upgrade head && python -m bot"]
