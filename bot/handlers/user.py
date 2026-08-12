"""Handlers for regular (non-admin) user interactions."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.constants import CODE_RE
from bot.db import crud
from bot.db.base import release_session
from bot.locales import TEXTS
from bot.services.telegram import safe_answer, safe_send_video

logger = logging.getLogger(__name__)

router = Router(name="user")


@router.message(CommandStart())
async def cmd_start(message: Message) -> None:
    """Greet the user and explain how to use the bot."""
    await safe_answer(message, TEXTS.WELCOME, parse_mode="HTML")


@router.message(F.text.regexp(CODE_RE))
async def handle_movie_code(message: Message, session: AsyncSession) -> None:
    """Look up a numeric code and send the corresponding video."""
    if message.from_user is None or message.text is None:
        return

    code = message.text.strip()
    user_id = message.from_user.id

    try:
        await crud.upsert_user_activity(session, user_id)
    except Exception:
        logger.exception("Failed to update user activity for user_id=%s", user_id)

    try:
        movie = await crud.get_movie_by_code(session, code)
    except Exception:
        logger.exception("DB error looking up movie code for user_id=%s", user_id)
        await safe_answer(message, TEXTS.GENERIC_ERROR)
        return

    if movie is None:
        await safe_answer(message, TEXTS.CODE_NOT_FOUND)
        return

    # Release DB connection before Telegram I/O (may sleep on flood control).
    file_id = movie.file_id
    caption = movie.title if movie.title else None
    await release_session(session)

    bot = message.bot
    if bot is None:
        logger.error(
            "message.bot is None; cannot deliver video user_id=%s",
            user_id,
        )
        return

    sent = await safe_send_video(
        bot,
        message.chat.id,
        file_id,
        caption=caption,
    )
    if sent is None:
        await safe_answer(message, TEXTS.VIDEO_UNAVAILABLE)
        logger.error(
            "Failed to deliver video to user_id=%s outcome=unavailable",
            user_id,
        )


@router.message(Command("list_codes", "delete_code", "stats", "auditlog"))
async def admin_commands_denied(message: Message) -> None:
    """Brief denial when a non-admin tries admin-only commands."""
    if message.from_user and get_settings().is_admin(message.from_user.id):
        return
    await safe_answer(message, TEXTS.ADMIN_ONLY)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_non_numeric_text(message: Message) -> None:
    """Guide users who send non-numeric text (not treated as an error)."""
    await safe_answer(message, TEXTS.GUIDANCE, parse_mode="HTML")
