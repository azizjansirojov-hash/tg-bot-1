"""Admin handlers: file_id capture FSM, list/delete codes, stats, audit log."""

from __future__ import annotations

import json
import logging
import math
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import F, Router
from aiogram.filters import Command, CommandObject, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message
from sqlalchemy.ext.asyncio import AsyncSession

from bot.config import get_settings
from bot.constants import CODE_RE, TITLE_MAX_LEN
from bot.db import crud
from bot.filters.admin import IsAdmin
from bot.keyboards.inline import (
    auditlog_keyboard,
    delete_confirm_keyboard,
    list_codes_keyboard,
    overwrite_confirm_keyboard,
    save_confirm_keyboard,
)
from bot.locales import TEXTS
from bot.services.telegram import safe_answer
from bot.states.admin_add import AdminAddMovie
from bot.utils.forward import (
    ForwardRejectReason,
    classify_video_forward_rejection,
    extract_storage_forward,
)
from bot.utils.html import escape_html

logger = logging.getLogger(__name__)

router = Router(name="admin")
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())

PER_PAGE = 10

# FSM data keys stored after a storage-channel forward
FSM_FILE_ID = "file_id"
FSM_CHANNEL_MSG_ID = "channel_message_id"
FSM_CODE = "code"
FSM_TITLE = "title"
FSM_OVERWRITE = "overwrite"

_REJECT_TEXTS = {
    ForwardRejectReason.NOT_A_FORWARD: TEXTS.ADMIN_VIDEO_REJECTED_NOT_FORWARD,
    ForwardRejectReason.WRONG_CHANNEL: TEXTS.ADMIN_VIDEO_REJECTED_WRONG_CHANNEL,
    ForwardRejectReason.FORWARDED_FROM_USER: TEXTS.ADMIN_VIDEO_REJECTED_FROM_USER,
    ForwardRejectReason.NO_VIDEO: TEXTS.ADMIN_VIDEO_REJECTED_NOT_FORWARD,
}


async def _save_movie(
    session: AsyncSession,
    *,
    code: str,
    title: str | None,
    file_id: str,
    channel_message_id: int,
    admin_id: int,
    overwrite: bool,
) -> None:
    await crud.upsert_movie(
        session,
        code=code,
        title=title,
        file_id=file_id,
        channel_message_id=channel_message_id,
        added_by=admin_id,
    )
    action = "overwrite_movie" if overwrite else "add_movie"
    await crud.write_audit_log(
        session,
        admin_id=admin_id,
        action=action,
        target=code,
        details=json.dumps(
            {
                "channel_message_id": channel_message_id,
                "has_title": title is not None,
            },
            separators=(",", ":"),
        ),
    )
    logger.info(
        "Admin mutation outcome=ok action=%s admin_id=%s",
        action,
        admin_id,
    )


def _success_text(
    code: str,
    title: str | None,
    channel_message_id: int,
) -> str:
    title_display = escape_html(title) if title else TEXTS.ADMIN_TITLE_NONE
    return TEXTS.ADMIN_SAVE_SUCCESS.format(
        code=escape_html(code),
        title=title_display,
        channel_message_id=channel_message_id,
    )


# ---------------------------------------------------------------------------
# Forward capture → FSM
# ---------------------------------------------------------------------------


@router.message(F.video, F.chat.type == "private", StateFilter(None))
async def admin_forward_video(message: Message, state: FSMContext) -> None:
    """Start add-movie flow when admin forwards a video from the storage channel."""
    settings = get_settings()
    extracted = extract_storage_forward(message, settings.storage_channel_id)
    if extracted is None:
        reason = classify_video_forward_rejection(
            message, settings.storage_channel_id
        )
        text = _REJECT_TEXTS.get(
            reason or ForwardRejectReason.NOT_A_FORWARD,
            TEXTS.ADMIN_VIDEO_REJECTED_NOT_FORWARD,
        )
        await safe_answer(message, text, parse_mode="HTML")
        logger.info(
            "Admin video rejected reason=%s admin_id=%s",
            (reason or ForwardRejectReason.NOT_A_FORWARD).value,
            message.from_user.id if message.from_user else "?",
        )
        return

    file_id, channel_message_id = extracted
    await state.set_state(AdminAddMovie.waiting_for_code)
    await state.update_data(
        {
            FSM_FILE_ID: file_id,
            FSM_CHANNEL_MSG_ID: channel_message_id,
            FSM_OVERWRITE: False,
        }
    )
    await safe_answer(message, TEXTS.ADMIN_VIDEO_RECEIVED, parse_mode="HTML")
    logger.info(
        "Admin add-movie flow started admin_id=%s",
        message.from_user.id if message.from_user else "?",
    )


@router.message(AdminAddMovie.waiting_for_code, F.text)
async def admin_receive_code(
    message: Message,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Validate the code; ask for overwrite if it already exists, else ask for title."""
    if message.text is None:
        return

    code = message.text.strip()
    if not CODE_RE.fullmatch(code):
        await safe_answer(message, TEXTS.ADMIN_CODE_DIGITS_ONLY, parse_mode="HTML")
        return

    existing = await crud.get_movie_by_code(session, code)
    await state.update_data({FSM_CODE: code})

    if existing is not None:
        await state.set_state(AdminAddMovie.confirming_overwrite)
        if existing.title:
            title_part = f" ({escape_html(existing.title)})"
        else:
            title_part = ""
        await safe_answer(
            message,
            TEXTS.ADMIN_CODE_EXISTS.format(
                code=escape_html(code),
                title_part=title_part,
            ),
            parse_mode="HTML",
            reply_markup=overwrite_confirm_keyboard(),
        )
        return

    await state.set_state(AdminAddMovie.waiting_for_title)
    await safe_answer(message, TEXTS.ADMIN_ASK_TITLE, parse_mode="HTML")


@router.callback_query(
    AdminAddMovie.confirming_overwrite,
    F.data.in_({"overwrite:yes", "overwrite:no"}),
)
async def admin_overwrite_callback(
    callback: CallbackQuery,
    state: FSMContext,
) -> None:
    """Handle Yes/No overwrite; authoritative code comes from FSM only."""
    if callback.data is None or callback.message is None:
        return

    parts = callback.data.split(":", 1)
    if len(parts) != 2:
        await callback.answer(TEXTS.ADMIN_INVALID_ACTION)
        return

    decision = parts[1]
    await callback.answer()

    data = await state.get_data()
    code = data.get(FSM_CODE)
    if not code:
        await state.clear()
        await callback.message.edit_text(  # type: ignore[union-attr]
            TEXTS.ADMIN_SESSION_ERROR,
            parse_mode="HTML",
        )
        return

    code_str = str(code)
    if decision == "no":
        await state.clear()
        await callback.message.edit_text(  # type: ignore[union-attr]
            TEXTS.ADMIN_OVERWRITE_CANCELLED.format(code=escape_html(code_str)),
            parse_mode="HTML",
        )
        logger.info(
            "Admin mutation outcome=cancelled action=overwrite admin_id=%s",
            callback.from_user.id,
        )
        return

    await state.update_data({FSM_OVERWRITE: True})
    await state.set_state(AdminAddMovie.waiting_for_title)
    await callback.message.edit_text(  # type: ignore[union-attr]
        TEXTS.ADMIN_OVERWRITE_CONFIRMED.format(code=escape_html(code_str)),
        parse_mode="HTML",
    )


@router.message(AdminAddMovie.waiting_for_title, F.text)
async def admin_receive_title(
    message: Message,
    state: FSMContext,
) -> None:
    """Store title in FSM and ask for explicit save confirmation (no DB write yet)."""
    if message.text is None or message.from_user is None:
        return

    raw_title = message.text.strip()
    if raw_title != "-" and len(raw_title) > TITLE_MAX_LEN:
        await safe_answer(
            message,
            TEXTS.ADMIN_TITLE_TOO_LONG.format(max_len=TITLE_MAX_LEN),
            parse_mode="HTML",
        )
        return

    title: str | None = None if raw_title == "-" else raw_title

    data = await state.get_data()
    code = data.get(FSM_CODE)
    file_id = data.get(FSM_FILE_ID)
    channel_message_id = data.get(FSM_CHANNEL_MSG_ID)

    if not code or not file_id or channel_message_id is None:
        await state.clear()
        await safe_answer(message, TEXTS.ADMIN_SESSION_ERROR)
        return

    await state.update_data({FSM_TITLE: title})
    await state.set_state(AdminAddMovie.confirming_save)
    title_display = escape_html(title) if title else TEXTS.ADMIN_TITLE_NONE
    await safe_answer(
        message,
        TEXTS.ADMIN_CONFIRM_SAVE.format(
            code=escape_html(str(code)),
            title=title_display,
        ),
        parse_mode="HTML",
        reply_markup=save_confirm_keyboard(),
    )


@router.callback_query(
    AdminAddMovie.confirming_save,
    F.data.in_({"save:yes", "save:no"}),
)
async def admin_save_callback(
    callback: CallbackQuery,
    state: FSMContext,
    session: AsyncSession,
) -> None:
    """Persist only after explicit Ha/Yo'q; code from FSM only."""
    if callback.data is None or callback.message is None:
        return

    parts = callback.data.split(":", 1)
    if len(parts) != 2:
        await callback.answer(TEXTS.ADMIN_INVALID_ACTION)
        return

    decision = parts[1]
    await callback.answer()

    if decision == "no":
        await state.clear()
        await callback.message.edit_text(  # type: ignore[union-attr]
            TEXTS.ADMIN_SAVE_CANCELLED,
            parse_mode="HTML",
        )
        logger.info(
            "Admin mutation outcome=cancelled action=save admin_id=%s",
            callback.from_user.id,
        )
        return

    data = await state.get_data()
    file_id = data.get(FSM_FILE_ID)
    channel_message_id = data.get(FSM_CHANNEL_MSG_ID)
    title = data.get(FSM_TITLE)
    overwrite = bool(data.get(FSM_OVERWRITE))
    stored_code = data.get(FSM_CODE)

    if not stored_code or not file_id or channel_message_id is None:
        await state.clear()
        await callback.message.edit_text(  # type: ignore[union-attr]
            TEXTS.ADMIN_SESSION_ERROR,
            parse_mode="HTML",
        )
        return

    try:
        await _save_movie(
            session,
            code=str(stored_code),
            title=title if isinstance(title, str) or title is None else str(title),
            file_id=str(file_id),
            channel_message_id=int(channel_message_id),
            admin_id=callback.from_user.id,
            overwrite=overwrite,
        )
    except Exception:
        logger.exception(
            "Admin mutation outcome=error action=save admin_id=%s",
            callback.from_user.id,
        )
        await state.clear()
        await callback.message.edit_text(  # type: ignore[union-attr]
            TEXTS.ADMIN_SAVE_FAILED,
            parse_mode="HTML",
        )
        return

    await state.clear()
    title_val = title if isinstance(title, str) or title is None else None
    await callback.message.edit_text(  # type: ignore[union-attr]
        _success_text(str(stored_code), title_val, int(channel_message_id)),
        parse_mode="HTML",
    )


@router.message(StateFilter(AdminAddMovie), Command("cancel"))
async def admin_cancel_fsm(message: Message, state: FSMContext) -> None:
    """Allow admins to abort the add-movie conversation."""
    await state.clear()
    await safe_answer(message, TEXTS.ADMIN_FSM_CANCELLED)


# ---------------------------------------------------------------------------
# Shared pagination helpers
# ---------------------------------------------------------------------------


async def _paginate_callback(
    callback: CallbackQuery,
    *,
    fetch: Callable[[int], Awaitable[tuple[list[Any], int]]],
    format_page: Callable[[list[Any], int, int, int], str],
    keyboard_fn: Callable[[int, int], InlineKeyboardMarkup],
) -> None:
    """Navigate a paginated admin list (list_codes / auditlog)."""
    if callback.data is None or callback.message is None:
        return

    try:
        page = int(callback.data.split(":", 1)[1])
    except (IndexError, ValueError):
        await callback.answer(TEXTS.ADMIN_INVALID_PAGE)
        return

    if page < 0:
        page = 0

    items, total = await fetch(page)
    total_pages = max(1, math.ceil(total / PER_PAGE)) if total else 1
    if page >= total_pages:
        page = total_pages - 1
        items, total = await fetch(page)

    text = format_page(items, page, total, total_pages)
    markup = keyboard_fn(page, total_pages) if total > PER_PAGE else None
    await callback.answer()
    await callback.message.edit_text(  # type: ignore[union-attr]
        text,
        parse_mode="HTML",
        reply_markup=markup,
    )


# ---------------------------------------------------------------------------
# /list_codes
# ---------------------------------------------------------------------------


def _format_list_page(movies: list, page: int, total: int, total_pages: int) -> str:
    if total == 0:
        return TEXTS.ADMIN_LIST_EMPTY

    lines = [
        TEXTS.ADMIN_LIST_HEADER.format(
            page=page + 1,
            total_pages=total_pages,
            total=total,
        )
    ]
    for movie in movies:
        title = escape_html(movie.title) if movie.title else "—"
        lines.append(
            TEXTS.ADMIN_LIST_ITEM.format(
                code=escape_html(movie.code),
                title=title,
            )
        )
    return "\n".join(lines)


@router.message(Command("list_codes"))
async def cmd_list_codes(message: Message, session: AsyncSession) -> None:
    """Show paginated list of all movie codes."""
    movies, total = await crud.list_movies_paginated(session, page=0, per_page=PER_PAGE)
    total_pages = max(1, math.ceil(total / PER_PAGE)) if total else 1
    text = _format_list_page(movies, 0, total, total_pages)
    markup = list_codes_keyboard(0, total_pages) if total > PER_PAGE else None
    await safe_answer(message, text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data.startswith("list_codes:"))
async def list_codes_page(callback: CallbackQuery, session: AsyncSession) -> None:
    """Navigate /list_codes pages."""

    async def fetch(page: int) -> tuple[list, int]:
        return await crud.list_movies_paginated(
            session, page=page, per_page=PER_PAGE
        )

    await _paginate_callback(
        callback,
        fetch=fetch,
        format_page=_format_list_page,
        keyboard_fn=list_codes_keyboard,
    )


# ---------------------------------------------------------------------------
# /delete_code
# ---------------------------------------------------------------------------


@router.message(Command("delete_code"))
async def cmd_delete_code(
    message: Message,
    command: CommandObject,
    session: AsyncSession,
) -> None:
    """Ask for confirmation before deleting a movie code."""
    args = (command.args or "").strip()
    if not args or not CODE_RE.fullmatch(args):
        await safe_answer(message, TEXTS.ADMIN_DELETE_USAGE, parse_mode="HTML")
        return

    movie = await crud.get_movie_by_code(session, args)
    if movie is None:
        await safe_answer(
            message,
            TEXTS.ADMIN_DELETE_NOT_FOUND.format(code=escape_html(args)),
            parse_mode="HTML",
        )
        return

    title = escape_html(movie.title) if movie.title else "—"
    await safe_answer(
        message,
        TEXTS.ADMIN_DELETE_CONFIRM.format(code=escape_html(args), title=title),
        parse_mode="HTML",
        reply_markup=delete_confirm_keyboard(args),
    )


@router.callback_query(F.data.startswith("delete:"))
async def delete_code_callback(
    callback: CallbackQuery,
    session: AsyncSession,
) -> None:
    """Confirm or cancel deletion."""
    if callback.data is None or callback.message is None:
        return

    parts = callback.data.split(":", 2)
    if len(parts) != 3:
        await callback.answer(TEXTS.ADMIN_INVALID_ACTION)
        return

    _, decision, code = parts
    await callback.answer()

    if decision == "no":
        await callback.message.edit_text(  # type: ignore[union-attr]
            TEXTS.ADMIN_DELETE_CANCELLED.format(code=escape_html(code)),
            parse_mode="HTML",
        )
        return

    deleted = await crud.delete_movie(session, code)
    if deleted:
        await crud.write_audit_log(
            session,
            admin_id=callback.from_user.id,
            action="delete_movie",
            target=code,
            details=None,
        )
        logger.info(
            "Admin mutation outcome=ok action=delete_movie admin_id=%s",
            callback.from_user.id,
        )
        await callback.message.edit_text(  # type: ignore[union-attr]
            TEXTS.ADMIN_DELETE_SUCCESS.format(code=escape_html(code)),
            parse_mode="HTML",
        )
    else:
        await callback.message.edit_text(  # type: ignore[union-attr]
            TEXTS.ADMIN_DELETE_ALREADY_GONE.format(code=escape_html(code)),
            parse_mode="HTML",
        )


# ---------------------------------------------------------------------------
# /stats
# ---------------------------------------------------------------------------


@router.message(Command("stats"))
async def cmd_stats(message: Message, session: AsyncSession) -> None:
    """Show total movies and unique requesting users."""
    movies = await crud.count_movies(session)
    users = await crud.count_users(session)
    await safe_answer(
        message,
        TEXTS.ADMIN_STATS.format(movies=movies, users=users),
        parse_mode="HTML",
    )


# ---------------------------------------------------------------------------
# /auditlog
# ---------------------------------------------------------------------------


def _format_audit_page(entries: list, page: int, total: int, total_pages: int) -> str:
    if total == 0:
        return TEXTS.ADMIN_AUDIT_EMPTY

    lines = [
        TEXTS.ADMIN_AUDIT_HEADER.format(
            page=page + 1,
            total_pages=total_pages,
            total=total,
        )
    ]
    for entry in entries:
        ts = entry.timestamp.strftime("%Y-%m-%d %H:%M:%S") if entry.timestamp else "—"
        lines.append(
            TEXTS.ADMIN_AUDIT_ITEM.format(
                timestamp=escape_html(ts),
                admin_id=entry.admin_id,
                action=escape_html(entry.action),
                target=escape_html(entry.target) if entry.target else "—",
            )
        )
    return "\n".join(lines)


@router.message(Command("auditlog"))
async def cmd_auditlog(message: Message, session: AsyncSession) -> None:
    """Show paginated admin audit log (newest first)."""
    entries, total = await crud.list_audit_logs_paginated(
        session, page=0, per_page=PER_PAGE
    )
    total_pages = max(1, math.ceil(total / PER_PAGE)) if total else 1
    text = _format_audit_page(entries, 0, total, total_pages)
    markup = auditlog_keyboard(0, total_pages) if total > PER_PAGE else None
    await safe_answer(message, text, parse_mode="HTML", reply_markup=markup)


@router.callback_query(F.data.startswith("auditlog:"))
async def auditlog_page(callback: CallbackQuery, session: AsyncSession) -> None:
    """Navigate /auditlog pages."""

    async def fetch(page: int) -> tuple[list, int]:
        return await crud.list_audit_logs_paginated(
            session, page=page, per_page=PER_PAGE
        )

    await _paginate_callback(
        callback,
        fetch=fetch,
        format_page=_format_audit_page,
        keyboard_fn=auditlog_keyboard,
    )
