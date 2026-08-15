"""English locale strings. Attribute names must match ``uz.Texts``."""

from __future__ import annotations

from bot.locales.uz import Texts as _BaseTexts


class Texts(_BaseTexts):
    """English overrides for all user-facing strings."""

    WELCOME = (
        "👋 Welcome!\n\n"
        "Send a movie code and I will send you the matching video.\n\n"
        "Just type the number — that simple!"
    )
    GUIDANCE = (
        "Please send the movie code as digits only.\n"
        "I only understand numeric codes."
    )
    CODE_NOT_FOUND = "Code not found. Check the number and try again."
    VIDEO_UNAVAILABLE = (
        "Sorry, this video is not available right now. Try again later "
        "or contact an admin."
    )
    GENERIC_ERROR = "Something went wrong. Please try again in a moment."
    ADMIN_ONLY = "This command is for admins only."
    RATE_LIMITED = (
        "You are sending requests too quickly. Wait about {seconds} seconds "
        "and try again."
    )

    HELP_HEADER = "<b>Commands</b>"
    HELP_ADMIN_HEADER = "<b>Admin commands</b>"
    CMD_START_DESC = "Short introduction to the bot"
    CMD_HELP_DESC = "List of available commands"
    CMD_LIST_CODES_DESC = "List stored codes"
    CMD_DELETE_CODE_DESC = "Delete a code"
    CMD_STATS_DESC = "Statistics"
    CMD_AUDITLOG_DESC = "Admin audit log"
    CMD_CANCEL_DESC = "Cancel the current admin action"
    CMD_LANGUAGE_DESC = "Change language"
    CMD_BROADCAST_DESC = "Send a message to all users"

    LANGUAGE_CHOICE = "Choose a language:"
    LANGUAGE_UPDATED = "Language set to English."
    START_LANGUAGE_PROMPT = (
        "Tilni tanlang / Выберите язык / Choose a language:"
    )
    BTN_LANG_UZ = "O‘zbekcha"
    BTN_LANG_RU = "Русский"
    BTN_LANG_EN = "English"

    ADMIN_VIDEO_RECEIVED = (
        "Video received from the storage channel.\n\n"
        "Enter a unique numeric code for this video (for example: <b>102</b>)."
    )
    ADMIN_VIDEO_REJECTED_NOT_FORWARD = (
        "Video was not accepted.\n\n"
        "Only videos <b>forwarded from the storage channel</b> can be added. "
        "Do not send a video directly — upload it to the storage channel first, "
        "then forward it to the bot."
    )
    ADMIN_VIDEO_REJECTED_WRONG_CHANNEL = (
        "Video was not accepted.\n\n"
        "This video is not from the configured storage channel. "
        "Forward only from the channel in <code>STORAGE_CHANNEL_ID</code>."
    )
    ADMIN_VIDEO_REJECTED_FROM_USER = (
        "Video was not accepted.\n\n"
        "Videos forwarded from a user are not accepted. "
        "Forward the video from the storage channel."
    )
    ADMIN_CODE_DIGITS_ONLY = (
        "The code must contain digits only "
        "(for example: <b>102</b>). Enter it again."
    )
    ADMIN_CODE_EXISTS = (
        "Code <b>{code}</b> already exists{title_part}.\n"
        "Replace it with the new video?"
    )
    ADMIN_ASK_TITLE = (
        "Good. Now send the movie title, or send <b>-</b> to skip."
    )
    ADMIN_TITLE_TOO_LONG = (
        "Title is too long (maximum {max_len} characters). "
        "Send a shorter title or <b>-</b> to skip."
    )
    ADMIN_CONFIRM_SAVE = (
        "Confirm save.\n\n"
        "<b>Code:</b> {code}\n"
        "<b>Title:</b> {title}\n\n"
        "Continue?"
    )
    ADMIN_SAVE_CANCELLED = "Save cancelled. Nothing was written."
    ADMIN_OVERWRITE_CANCELLED = (
        "Cancelled. Code <b>{code}</b> was not changed."
    )
    ADMIN_OVERWRITE_CONFIRMED = (
        "Overwrite of <b>{code}</b> confirmed.\n"
        "Now send a title or <b>-</b> to skip."
    )
    ADMIN_SESSION_ERROR = (
        "A session error occurred. Forward the video again."
    )
    ADMIN_SAVE_FAILED = "Save failed. Please try again."
    ADMIN_SAVE_SUCCESS = (
        "✅ Movie saved successfully!\n\n"
        "<b>Code:</b> {code}\n"
        "<b>Title:</b> {title}\n"
        "<b>Channel message ID:</b> {channel_message_id}"
    )
    ADMIN_TITLE_NONE = "(none)"
    ADMIN_FSM_CANCELLED = "Cancelled. Nothing was saved."
    ADMIN_INVALID_ACTION = "Invalid action."

    ADMIN_LIST_EMPTY = "No movies stored yet."
    ADMIN_LIST_HEADER = (
        "<b>Stored codes</b> "
        "(page {page}/{total_pages}, total {total}):\n"
    )
    ADMIN_LIST_ITEM = "• <code>{code}</code> — {title}"
    ADMIN_DELETE_USAGE = "Usage: <code>/delete_code 102</code>"
    ADMIN_DELETE_NOT_FOUND = "Code <b>{code}</b> was not found."
    ADMIN_DELETE_CONFIRM = (
        "Delete code <b>{code}</b> ({title})?\n"
        "This cannot be undone."
    )
    ADMIN_DELETE_CANCELLED = (
        "Delete cancelled. Code <b>{code}</b> was kept."
    )
    ADMIN_DELETE_SUCCESS = "🗑 Code <b>{code}</b> was deleted."
    ADMIN_DELETE_ALREADY_GONE = (
        "Code <b>{code}</b> was not found (it may already be deleted)."
    )
    ADMIN_STATS = (
        "📊 <b>Statistics</b>\n\n"
        "Stored movies: <b>{movies}</b>\n"
        "Users who requested a code: <b>{users}</b>"
    )
    ADMIN_INVALID_PAGE = "Invalid page."
    ADMIN_AUDIT_EMPTY = "The audit log is empty."
    ADMIN_AUDIT_HEADER = (
        "<b>Admin audit log</b> "
        "(page {page}/{total_pages}, total {total}):\n"
    )
    ADMIN_AUDIT_ITEM = (
        "• <code>{timestamp}</code> | admin=<code>{admin_id}</code> | "
        "<b>{action}</b> | target=<code>{target}</code>"
    )

    BTN_PREV = "« Previous"
    BTN_NEXT = "Next »"
    BTN_OVERWRITE_YES = "Yes, overwrite"
    BTN_OVERWRITE_NO = "Cancel"
    BTN_DELETE_YES = "Yes, delete"
    BTN_DELETE_NO = "No, cancel"
    BTN_SAVE_YES = "Yes, save"
    BTN_SAVE_NO = "No, cancel"
    BTN_BROADCAST_YES = "Yes, send"
    BTN_BROADCAST_NO = "No, cancel"

    ADMIN_BROADCAST_ASK = (
        "Send the message text (plain text only).\n"
        "Cancel with /cancel"
    )
    ADMIN_BROADCAST_EMPTY = "There are no active users to send to."
    ADMIN_BROADCAST_CONFIRM = (
        "This will send to <b>{count}</b> users. Confirm?"
    )
    ADMIN_BROADCAST_CANCELLED = "Broadcast cancelled. Nobody was messaged."
    ADMIN_BROADCAST_TEXT_TOO_LONG = (
        "Text is too long (maximum {max_len} characters). Send a shorter message."
    )
    ADMIN_BROADCAST_NEED_TEXT = (
        "Please send some text (empty messages are not allowed)."
    )
    ADMIN_BROADCAST_SUMMARY = (
        "📣 <b>Broadcast finished</b>\n\n"
        "Attempted: <b>{attempted}</b>\n"
        "Succeeded: <b>{succeeded}</b>\n"
        "Blocked: <b>{failed_blocked}</b>\n"
        "Other failures: <b>{failed_other}</b>\n"
        "Duration: <b>{duration_ms}</b> ms"
    )


TEXTS = Texts()
