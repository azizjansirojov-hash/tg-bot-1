"""Paced admin broadcast send loop (Telegram flood-aware)."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramRetryAfter

from bot.constants import BROADCAST_SENDS_PER_SECOND

logger = logging.getLogger(__name__)


@dataclass
class BroadcastResult:
    """Counts from one broadcast run (no message bodies)."""

    attempted: int = 0
    succeeded: int = 0
    failed_blocked: int = 0
    failed_other: int = 0
    duration_ms: int = 0
    blocked_ids: list[int] = field(default_factory=list)


async def send_broadcast(
    bot: Bot,
    chat_ids: list[int],
    text: str,
    *,
    sends_per_second: int = BROADCAST_SENDS_PER_SECOND,
) -> BroadcastResult:
    """
    Send ``text`` to each chat, pacing outbound messages.

    ``TelegramRetryAfter`` pauses and retries that chat once.
    ``TelegramForbiddenError`` skips the chat and records it as blocked.
    Other errors skip the chat. The loop never aborts the rest of the batch.
    """
    result = BroadcastResult(attempted=len(chat_ids))
    started = time.monotonic()
    delay = 1.0 / max(1, sends_per_second)

    for chat_id in chat_ids:
        outcome = await _send_one(bot, chat_id, text)
        if outcome == "ok":
            result.succeeded += 1
        elif outcome == "blocked":
            result.failed_blocked += 1
            result.blocked_ids.append(chat_id)
        else:
            result.failed_other += 1
        await asyncio.sleep(delay)

    result.duration_ms = int((time.monotonic() - started) * 1000)
    logger.info(
        "Broadcast finished attempted=%s succeeded=%s blocked=%s "
        "other=%s duration_ms=%s",
        result.attempted,
        result.succeeded,
        result.failed_blocked,
        result.failed_other,
        result.duration_ms,
    )
    return result


async def _send_one(bot: Bot, chat_id: int, text: str) -> str:
    try:
        await bot.send_message(chat_id=chat_id, text=text, parse_mode=None)
        return "ok"
    except TelegramRetryAfter as exc:
        logger.warning(
            "Broadcast flood wait chat_id=%s retry_after=%s",
            chat_id,
            exc.retry_after,
        )
        await asyncio.sleep(exc.retry_after)
        try:
            await bot.send_message(chat_id=chat_id, text=text, parse_mode=None)
            return "ok"
        except TelegramForbiddenError:
            logger.warning("Broadcast blocked after retry chat_id=%s", chat_id)
            return "blocked"
        except Exception:
            logger.exception("Broadcast retry failed chat_id=%s", chat_id)
            return "other"
    except TelegramForbiddenError:
        logger.warning("Broadcast skipped blocked user chat_id=%s", chat_id)
        return "blocked"
    except Exception:
        logger.exception("Broadcast send failed chat_id=%s", chat_id)
        return "other"
