"""Per-update SQLAlchemy session middleware."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession

from bot.db.base import get_session_factory


class DbSessionMiddleware(BaseMiddleware):
    """Inject an AsyncSession as `session` into handler kwargs."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        session: AsyncSession = get_session_factory()()
        data["session"] = session
        try:
            result = await handler(event, data)
            # Handler may have released the session early (before flood-wait).
            if session.is_active:
                await session.commit()
            return result
        except Exception:
            if session.is_active:
                await session.rollback()
            raise
        finally:
            if session.is_active:
                await session.close()
