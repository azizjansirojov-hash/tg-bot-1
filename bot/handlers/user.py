"""Handlers for regular (non-admin) user interactions."""

from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.commands import format_help_text
from bot.config import get_settings
from bot.constants import CODE_RE
from bot.db import crud
from bot.db.base import release_session
from bot.keyboards.inline import language_keyboard
from bot.locales import SUPPORTED_LANGUAGES, TEXTS, Texts, get_texts, normalize_language
from bot.services.telegram import safe_answer, safe_send_video
from bot.utils.forward import extract_storage_forward

logger = logging.getLogger(__name__)

router = Router(name="user")


async def _ensure_user_quiet(session: AsyncSession | None, message: Message) -> None:
    if session is None or message.from_user is None:
        return
    try:
        await crud.ensure_user(
            session,
            message.from_user.id,
            message.from_user.language_code,
        )
    except Exception:
        logger.exception(
            "Failed to ensure user user_id=%s",
            message.from_user.id,
        )


async def _send_start_content(message: Message, texts: Texts) -> None:
    """Normal /start body (welcome) after language is known."""
    await safe_answer(message, texts.WELCOME, parse_mode="HTML")


@router.message(CommandStart())
async def cmd_start(
    message: Message,
    texts: Texts = TEXTS,
    session: AsyncSession | None = None,
) -> None:
    """Greet the user; first-time users pick a language before welcome."""
    if session is not None and message.from_user is not None:
        stored: str | None = None
        try:
            stored = await crud.get_user_language(session, message.from_user.id)
        except Exception:
            logger.exception(
                "Failed to load language on /start user_id=%s",
                message.from_user.id,
            )
            stored = ""
        if stored is None:
            await safe_answer(
                message,
                texts.START_LANGUAGE_PROMPT,
                parse_mode="HTML",
                reply_markup=language_keyboard(texts),
            )
            return
    await _ensure_user_quiet(session, message)
    await _send_start_content(message, texts)


@router.message(Command("help"))
async def cmd_help(
    message: Message,
    texts: Texts = TEXTS,
    session: AsyncSession | None = None,
) -> None:
    """List commands the current user is allowed to use."""
    await _ensure_user_quiet(session, message)
    is_admin = bool(
        message.from_user and get_settings().is_admin(message.from_user.id)
    )
    await safe_answer(
        message,
        format_help_text(texts, is_admin=is_admin),
        parse_mode="HTML",
    )


@router.message(Command("language"))
async def cmd_language(
    message: Message,
    texts: Texts = TEXTS,
    session: AsyncSession | None = None,
) -> None:
    """Offer supported languages on an inline keyboard."""
    await _ensure_user_quiet(session, message)
    await safe_answer(
        message,
        texts.LANGUAGE_CHOICE,
        parse_mode="HTML",
        reply_markup=language_keyboard(texts),
    )


@router.callback_query(F.data.startswith("lang:"))
async def language_chosen(
    callback: CallbackQuery,
    session: AsyncSession,
    texts: Texts = TEXTS,
) -> None:
    """Persist an explicit language choice and reply in that language."""
    if callback.data is None or callback.from_user is None:
        return
    parts = callback.data.split(":", 1)
    if len(parts) != 2 or parts[1] not in SUPPORTED_LANGUAGES:
        await callback.answer(texts.ADMIN_INVALID_ACTION)
        return
    lang = normalize_language(parts[1])
    was_new = False
    try:
        stored = await crud.get_user_language(session, callback.from_user.id)
        was_new = stored is None
    except Exception:
        logger.exception(
            "Failed to load language before set user_id=%s",
            callback.from_user.id,
        )
    try:
        await crud.set_user_language(session, callback.from_user.id, lang)
    except Exception:
        logger.exception(
            "Failed to set language user_id=%s",
            callback.from_user.id,
        )
        await callback.answer(texts.GENERIC_ERROR, show_alert=True)
        return

    new_texts = get_texts(lang)
    await callback.answer()
    if callback.message is not None:
        await callback.message.edit_text(  # type: ignore[union-attr]
            new_texts.LANGUAGE_UPDATED,
            parse_mode="HTML",
        )
        if was_new:
            await _send_start_content(callback.message, new_texts)  # type: ignore[arg-type]


@router.message(F.text.regexp(CODE_RE))
async def handle_movie_code(
    message: Message,
    session: AsyncSession,
    texts: Texts = TEXTS,
) -> None:
    """Look up a numeric code and send the corresponding video."""
    if message.from_user is None or message.text is None:
        return

    code = message.text.strip()
    user_id = message.from_user.id

    try:
        await crud.upsert_user_activity(
            session,
            user_id,
            message.from_user.language_code,
        )
    except Exception:
        logger.exception("Failed to update user activity for user_id=%s", user_id)

    try:
        movie = await crud.get_movie_by_code(session, code)
    except Exception:
        logger.exception("DB error looking up movie code for user_id=%s", user_id)
        await safe_answer(message, texts.GENERIC_ERROR)
        return

    if movie is None:
        await safe_answer(message, texts.CODE_NOT_FOUND)
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
        await safe_answer(message, texts.VIDEO_UNAVAILABLE)
        logger.error(
            "Failed to deliver video to user_id=%s outcome=unavailable",
            user_id,
        )


@router.message(
    Command("list_codes", "delete_code", "stats", "auditlog", "broadcast", "cancel")
)
async def admin_commands_denied(
    message: Message,
    texts: Texts = TEXTS,
) -> None:
    """Brief denial when a non-admin tries admin-only commands."""
    if message.from_user and get_settings().is_admin(message.from_user.id):
        return
    await safe_answer(message, texts.ADMIN_ONLY)


@router.message(F.video, F.chat.type == "private")
async def admin_storage_forward_denied(
    message: Message,
    texts: Texts = TEXTS,
) -> None:
    """Deny add-movie forwards from non-admins; ignore ordinary videos."""
    if message.from_user and get_settings().is_admin(message.from_user.id):
        return
    settings = get_settings()
    if extract_storage_forward(message, settings.storage_channel_id) is None:
        return
    await safe_answer(message, texts.ADMIN_ONLY)


@router.message(F.text & ~F.text.startswith("/"))
async def handle_non_numeric_text(
    message: Message,
    texts: Texts = TEXTS,
) -> None:
    """Guide users who send non-numeric text (not treated as an error)."""
    await safe_answer(message, texts.GUIDANCE, parse_mode="HTML")
