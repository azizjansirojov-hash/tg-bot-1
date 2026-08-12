"""Admin-only filter based on ADMIN_IDS from settings."""

from __future__ import annotations

from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, Message

from bot.config import get_settings


class IsAdmin(BaseFilter):
    """Allow only Telegram users listed in ADMIN_IDS."""

    async def __call__(self, event: Message | CallbackQuery) -> bool:
        user = event.from_user
        if user is None:
            return False
        return get_settings().is_admin(user.id)
