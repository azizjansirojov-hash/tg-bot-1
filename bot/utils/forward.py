"""Pure helpers for validating storage-channel video forwards."""

from __future__ import annotations

from enum import Enum

from aiogram.types import Message, MessageOriginChannel, MessageOriginUser


class ForwardRejectReason(str, Enum):
    """Why a video message was rejected for the add-movie flow."""

    NOT_A_FORWARD = "not_a_forward"
    WRONG_CHANNEL = "wrong_channel"
    FORWARDED_FROM_USER = "forwarded_from_user"
    NO_VIDEO = "no_video"


def extract_storage_forward(
    message: Message,
    storage_channel_id: int,
) -> tuple[str, int] | None:
    """
    If this message is a video forwarded from the storage channel, return
    (file_id, channel_message_id). Otherwise return None.

    Prefer Bot API 7+ forward_origin; fall back to legacy forward_from_chat.
    Channel ID comparison uses exact equality (==), never substring matching.
    """
    if message.video is None:
        return None

    file_id = message.video.file_id
    channel_message_id: int | None = None

    origin = message.forward_origin
    if isinstance(origin, MessageOriginChannel):
        if origin.chat.id == storage_channel_id:
            channel_message_id = origin.message_id
    elif message.forward_from_chat is not None:
        # Legacy attribute still present on some clients / aiogram versions
        if message.forward_from_chat.id == storage_channel_id:
            channel_message_id = message.forward_from_message_id

    if channel_message_id is None:
        return None
    return file_id, channel_message_id


def classify_video_forward_rejection(
    message: Message,
    storage_channel_id: int,
) -> ForwardRejectReason | None:
    """
    Return a rejection reason when the video is NOT a valid storage-channel forward.

    Returns None when extract_storage_forward would succeed.
    """
    if message.video is None:
        return ForwardRejectReason.NO_VIDEO

    if extract_storage_forward(message, storage_channel_id) is not None:
        return None

    origin = message.forward_origin
    if isinstance(origin, MessageOriginUser):
        return ForwardRejectReason.FORWARDED_FROM_USER

    if isinstance(origin, MessageOriginChannel):
        # Exact equality already failed inside extract_storage_forward.
        if origin.chat.id != storage_channel_id:
            return ForwardRejectReason.WRONG_CHANNEL

    if message.forward_from_chat is not None:
        if message.forward_from_chat.id != storage_channel_id:
            return ForwardRejectReason.WRONG_CHANNEL

    # No forward markers at all (uploaded / sent directly), or unrecognized origin.
    if origin is None and message.forward_from_chat is None:
        return ForwardRejectReason.NOT_A_FORWARD

    # Forwarded from a user via legacy fields, or other non-channel origin.
    return ForwardRejectReason.FORWARDED_FROM_USER
