"""Unit tests for storage-channel forward extraction and rejection classification."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from aiogram.enums import ChatType
from aiogram.types import (
    Chat,
    Message,
    MessageOriginChannel,
    MessageOriginUser,
    User,
    Video,
)
from bot.utils.forward import (
    ForwardRejectReason,
    classify_video_forward_rejection,
    extract_storage_forward,
)

STORAGE_CHANNEL_ID = -1001234567890
WRONG_CHANNEL_ID = -1009999999999


def _video() -> Video:
    return Video(
        file_id="BAACAgIAAxkBAAIfakeFileIdForTests123456",
        file_unique_id="unique123",
        width=1280,
        height=720,
        duration=10,
    )


def _make_message(**overrides: Any) -> Message:
    """Build a minimal Message; unset forward fields default to None."""
    base: dict[str, Any] = {
        "message_id": 1,
        "date": datetime.now(timezone.utc),
        "chat": Chat(id=111, type=ChatType.PRIVATE),
        "from_user": User(id=42, is_bot=False, first_name="Admin"),
        "video": _video(),
        "forward_origin": None,
        "forward_from_chat": None,
        "forward_from_message_id": None,
    }
    base.update(overrides)
    return Message(**base)


def test_legit_channel_forward_bot_api_7() -> None:
    origin = MessageOriginChannel(
        type="channel",
        date=datetime.now(timezone.utc),
        chat=Chat(id=STORAGE_CHANNEL_ID, type=ChatType.CHANNEL, title="Storage"),
        message_id=777,
    )
    msg = _make_message(forward_origin=origin)
    result = extract_storage_forward(msg, STORAGE_CHANNEL_ID)
    assert result is not None
    file_id, channel_msg_id = result
    assert file_id == msg.video.file_id  # type: ignore[union-attr]
    assert channel_msg_id == 777
    assert classify_video_forward_rejection(msg, STORAGE_CHANNEL_ID) is None


def test_legit_channel_forward_legacy() -> None:
    msg = _make_message(
        forward_from_chat=Chat(
            id=STORAGE_CHANNEL_ID, type=ChatType.CHANNEL, title="Storage"
        ),
        forward_from_message_id=888,
    )
    result = extract_storage_forward(msg, STORAGE_CHANNEL_ID)
    assert result == (msg.video.file_id, 888)  # type: ignore[union-attr]
    assert classify_video_forward_rejection(msg, STORAGE_CHANNEL_ID) is None


def test_wrong_channel_bot_api_7() -> None:
    origin = MessageOriginChannel(
        type="channel",
        date=datetime.now(timezone.utc),
        chat=Chat(id=WRONG_CHANNEL_ID, type=ChatType.CHANNEL, title="Other"),
        message_id=1,
    )
    msg = _make_message(forward_origin=origin)
    assert extract_storage_forward(msg, STORAGE_CHANNEL_ID) is None
    assert (
        classify_video_forward_rejection(msg, STORAGE_CHANNEL_ID)
        == ForwardRejectReason.WRONG_CHANNEL
    )


def test_wrong_channel_legacy() -> None:
    msg = _make_message(
        forward_from_chat=Chat(
            id=WRONG_CHANNEL_ID, type=ChatType.CHANNEL, title="Other"
        ),
        forward_from_message_id=1,
    )
    assert extract_storage_forward(msg, STORAGE_CHANNEL_ID) is None
    assert (
        classify_video_forward_rejection(msg, STORAGE_CHANNEL_ID)
        == ForwardRejectReason.WRONG_CHANNEL
    )


def test_not_a_forward() -> None:
    msg = _make_message()
    assert extract_storage_forward(msg, STORAGE_CHANNEL_ID) is None
    assert (
        classify_video_forward_rejection(msg, STORAGE_CHANNEL_ID)
        == ForwardRejectReason.NOT_A_FORWARD
    )


def test_forwarded_from_user() -> None:
    origin = MessageOriginUser(
        type="user",
        date=datetime.now(timezone.utc),
        sender_user=User(id=99, is_bot=False, first_name="Someone"),
    )
    msg = _make_message(forward_origin=origin)
    assert extract_storage_forward(msg, STORAGE_CHANNEL_ID) is None
    assert (
        classify_video_forward_rejection(msg, STORAGE_CHANNEL_ID)
        == ForwardRejectReason.FORWARDED_FROM_USER
    )


def test_channel_id_exact_equality_not_substring() -> None:
    """Ensure we never match via contains/substring — only exact ==."""
    # A channel id that merely contains the digits of STORAGE_CHANNEL_ID
    # as a substring of its string form must still fail exact equality.
    almost = int(str(STORAGE_CHANNEL_ID) + "0")
    origin = MessageOriginChannel(
        type="channel",
        date=datetime.now(timezone.utc),
        chat=Chat(id=almost, type=ChatType.CHANNEL, title="Almost"),
        message_id=1,
    )
    msg = _make_message(forward_origin=origin)
    assert STORAGE_CHANNEL_ID != almost
    assert extract_storage_forward(msg, STORAGE_CHANNEL_ID) is None


def test_code_re_max_length() -> None:
    from bot.constants import CODE_MAX_LEN, CODE_RE

    assert CODE_RE.fullmatch("1")
    assert CODE_RE.fullmatch("0" * CODE_MAX_LEN)
    assert CODE_RE.fullmatch("0" * (CODE_MAX_LEN + 1)) is None
    assert CODE_RE.fullmatch("12ab") is None
