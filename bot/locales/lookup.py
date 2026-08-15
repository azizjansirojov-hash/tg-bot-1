"""Short-lived DB lookup for a stored language preference."""

from __future__ import annotations

import logging

from bot.db import crud
from bot.db.base import get_session_factory

logger = logging.getLogger(__name__)


async def load_stored_language(telegram_id: int) -> str | None:
    """
    Return the user's stored language_code, or None.

    Opens its own short-lived session so callers that run before
    DbSessionMiddleware (rate-limit notices, the global error handler)
    can still honour an explicit preference. Never raises.
    """
    try:
        session = get_session_factory()()
        try:
            return await crud.get_user_language(session, telegram_id)
        finally:
            if session.is_active:
                await session.close()
    except Exception:
        logger.exception(
            "Failed to load stored language user_id=%s",
            telegram_id,
        )
        return None
