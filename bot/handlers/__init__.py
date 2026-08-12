"""Handler routers registration."""

from __future__ import annotations

from aiogram import Dispatcher

from bot.handlers.admin import router as admin_router
from bot.handlers.user import router as user_router


def register_routers(dp: Dispatcher) -> None:
    """Attach all routers to the dispatcher. Admin before user for FSM priority."""
    dp.include_router(admin_router)
    dp.include_router(user_router)
