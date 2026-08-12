"""Inline keyboards for admin flows."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.locales import TEXTS


def pagination_keyboard(
    prefix: str,
    page: int,
    total_pages: int,
) -> InlineKeyboardMarkup:
    """Shared Prev/Next controls; callback_data is ``{prefix}:{page}``."""
    builder = InlineKeyboardBuilder()
    buttons: list[InlineKeyboardButton] = []

    if page > 0:
        buttons.append(
            InlineKeyboardButton(
                text=TEXTS.BTN_PREV,
                callback_data=f"{prefix}:{page - 1}",
            )
        )
    if page < total_pages - 1:
        buttons.append(
            InlineKeyboardButton(
                text=TEXTS.BTN_NEXT,
                callback_data=f"{prefix}:{page + 1}",
            )
        )

    if buttons:
        builder.row(*buttons)
    return builder.as_markup()


def list_codes_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Pagination controls for /list_codes."""
    return pagination_keyboard("list_codes", page, total_pages)


def auditlog_keyboard(page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Pagination controls for /auditlog."""
    return pagination_keyboard("auditlog", page, total_pages)


def overwrite_confirm_keyboard() -> InlineKeyboardMarkup:
    """Yes/No for overwriting; code comes from FSM, not callback payload."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=TEXTS.BTN_OVERWRITE_YES,
            callback_data="overwrite:yes",
        ),
        InlineKeyboardButton(
            text=TEXTS.BTN_OVERWRITE_NO,
            callback_data="overwrite:no",
        ),
    )
    return builder.as_markup()


def save_confirm_keyboard() -> InlineKeyboardMarkup:
    """Yes/No before persist; code comes from FSM, not callback payload."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=TEXTS.BTN_SAVE_YES,
            callback_data="save:yes",
        ),
        InlineKeyboardButton(
            text=TEXTS.BTN_SAVE_NO,
            callback_data="save:no",
        ),
    )
    return builder.as_markup()


def delete_confirm_keyboard(code: str) -> InlineKeyboardMarkup:
    """Yes/No confirmation before deleting a code (stateless; code in payload)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=TEXTS.BTN_DELETE_YES,
            callback_data=f"delete:yes:{code}",
        ),
        InlineKeyboardButton(
            text=TEXTS.BTN_DELETE_NO,
            callback_data=f"delete:no:{code}",
        ),
    )
    return builder.as_markup()
