"""Safe wrappers around Telegram Bot API calls."""

from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramNetworkError,
    TelegramRetryAfter,
)
from aiogram.types import Message

logger = logging.getLogger(__name__)


async def safe_send_video(
    bot: Bot,
    chat_id: int,
    file_id: str,
    *,
    caption: str | None = None,
) -> Message | None:
    """
    Send a video by file_id with specific error handling.

    Captions are always plain text (parse_mode=None) so movie titles
    never go through HTML parsing — titles may contain <, &, etc.

    Never raises to the caller for expected Telegram failures.
    Never logs file_id or caption content at INFO+ levels.
    """
    try:
        return await bot.send_video(
            chat_id=chat_id,
            video=file_id,
            caption=caption,
            parse_mode=None,
        )
    except TelegramForbiddenError:
        logger.warning("Bot blocked by user chat_id=%s", chat_id)
    except TelegramRetryAfter as exc:
        logger.warning(
            "Flood control for chat_id=%s, retry after %s seconds",
            chat_id,
            exc.retry_after,
        )
        await asyncio.sleep(exc.retry_after)
        try:
            return await bot.send_video(
                chat_id=chat_id,
                video=file_id,
                caption=caption,
                parse_mode=None,
            )
        except Exception:
            logger.exception("Retry send_video failed for chat_id=%s", chat_id)
    except TelegramBadRequest:
        logger.error(
            "send_video BadRequest for chat_id=%s outcome=bad_request",
            chat_id,
        )
    except TelegramNetworkError:
        logger.exception("Network error sending video to chat_id=%s", chat_id)
    except Exception:
        logger.exception("Unexpected error sending video to chat_id=%s", chat_id)
    return None


async def safe_answer(message: Message, text: str, **kwargs: object) -> Message | None:
    """Reply to a message without letting Telegram errors crash the handler."""
    try:
        return await message.answer(text, **kwargs)  # type: ignore[arg-type]
    except TelegramForbiddenError:
        logger.warning(
            "Cannot answer: bot blocked by user chat_id=%s",
            message.chat.id,
        )
    except TelegramRetryAfter as exc:
        logger.warning(
            "Flood control answering chat_id=%s, wait %s s",
            message.chat.id,
            exc.retry_after,
        )
        await asyncio.sleep(exc.retry_after)
        try:
            return await message.answer(text, **kwargs)  # type: ignore[arg-type]
        except Exception:
            logger.exception("Retry answer failed for chat_id=%s", message.chat.id)
    except TelegramBadRequest as exc:
        logger.error("BadRequest answering chat_id=%s: %s", message.chat.id, exc)
    except Exception:
        logger.exception("Unexpected error answering chat_id=%s", message.chat.id)
    return None
