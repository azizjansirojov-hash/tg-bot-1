"""Inline keyboards for admin flows and language selection."""

from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from bot.locales import TEXTS, Texts


def pagination_keyboard(
    prefix: str,
    page: int,
    total_pages: int,
    texts: Texts = TEXTS,
) -> InlineKeyboardMarkup:
    """Shared Prev/Next controls; callback_data is ``{prefix}:{page}``."""
    builder = InlineKeyboardBuilder()
    buttons: list[InlineKeyboardButton] = []

    if page > 0:
        buttons.append(
            InlineKeyboardButton(
                text=texts.BTN_PREV,
                callback_data=f"{prefix}:{page - 1}",
            )
        )
    if page < total_pages - 1:
        buttons.append(
            InlineKeyboardButton(
                text=texts.BTN_NEXT,
                callback_data=f"{prefix}:{page + 1}",
            )
        )

    if buttons:
        builder.row(*buttons)
    return builder.as_markup()


def list_codes_keyboard(
    page: int,
    total_pages: int,
    texts: Texts = TEXTS,
) -> InlineKeyboardMarkup:
    """Pagination controls for /list_codes."""
    return pagination_keyboard("list_codes", page, total_pages, texts)


def auditlog_keyboard(
    page: int,
    total_pages: int,
    texts: Texts = TEXTS,
) -> InlineKeyboardMarkup:
    """Pagination controls for /auditlog."""
    return pagination_keyboard("auditlog", page, total_pages, texts)


def overwrite_confirm_keyboard(texts: Texts = TEXTS) -> InlineKeyboardMarkup:
    """Yes/No for overwriting; code comes from FSM, not callback payload."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=texts.BTN_OVERWRITE_YES,
            callback_data="overwrite:yes",
        ),
        InlineKeyboardButton(
            text=texts.BTN_OVERWRITE_NO,
            callback_data="overwrite:no",
        ),
    )
    return builder.as_markup()


def save_confirm_keyboard(texts: Texts = TEXTS) -> InlineKeyboardMarkup:
    """Yes/No before persist; code comes from FSM, not callback payload."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=texts.BTN_SAVE_YES,
            callback_data="save:yes",
        ),
        InlineKeyboardButton(
            text=texts.BTN_SAVE_NO,
            callback_data="save:no",
        ),
    )
    return builder.as_markup()


def delete_confirm_keyboard(code: str, texts: Texts = TEXTS) -> InlineKeyboardMarkup:
    """Yes/No confirmation before deleting a code (stateless; code in payload)."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=texts.BTN_DELETE_YES,
            callback_data=f"delete:yes:{code}",
        ),
        InlineKeyboardButton(
            text=texts.BTN_DELETE_NO,
            callback_data=f"delete:no:{code}",
        ),
    )
    return builder.as_markup()


def language_keyboard(texts: Texts = TEXTS) -> InlineKeyboardMarkup:
    """Supported languages for /language."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text=texts.BTN_LANG_UZ, callback_data="lang:uz"),
        InlineKeyboardButton(text=texts.BTN_LANG_RU, callback_data="lang:ru"),
        InlineKeyboardButton(text=texts.BTN_LANG_EN, callback_data="lang:en"),
    )
    return builder.as_markup()


def broadcast_confirm_keyboard(texts: Texts = TEXTS) -> InlineKeyboardMarkup:
    """Yes/No before sending a broadcast; body lives in FSM only."""
    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(
            text=texts.BTN_BROADCAST_YES,
            callback_data="broadcast:yes",
        ),
        InlineKeyboardButton(
            text=texts.BTN_BROADCAST_NO,
            callback_data="broadcast:no",
        ),
    )
    return builder.as_markup()
