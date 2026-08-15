"""Resolve locale strings for the acting user and inject ``texts``."""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject, Update

from bot.db import crud
from bot.locales import Texts, get_texts

logger = logging.getLogger(__name__)


def telegram_user_from_event(event: TelegramObject) -> Any | None:
    """Return ``from_user`` from an Update, Message, or CallbackQuery."""
    if isinstance(event, Update):
        if event.message and event.message.from_user:
            return event.message.from_user
        if event.callback_query and event.callback_query.from_user:
            return event.callback_query.from_user
        if event.edited_message and event.edited_message.from_user:
            return event.edited_message.from_user
        return None
    if isinstance(event, Message) and event.from_user:
        return event.from_user
    if isinstance(event, CallbackQuery) and event.from_user:
        return event.from_user
    return None


class UserLocaleMiddleware(BaseMiddleware):
    """Inject ``texts`` from stored preference, else Telegram language_code."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user = telegram_user_from_event(event)
        stored: str | None = None
        session = data.get("session")
        if user is not None and session is not None:
            try:
                stored = await crud.get_user_language(session, user.id)
            except Exception:
                logger.exception(
                    "Failed to load user language user_id=%s",
                    user.id,
                )
        telegram_code = getattr(user, "language_code", None) if user else None
        texts: Texts = get_texts(stored or telegram_code)
        data["texts"] = texts
        return await handler(event, data)
