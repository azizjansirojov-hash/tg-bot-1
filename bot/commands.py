"""Single source of truth for bot slash commands (help text + Telegram menu)."""

from __future__ import annotations

from dataclasses import dataclass

from aiogram.types import BotCommand

from bot.locales import Texts


@dataclass(frozen=True)
class CommandSpec:
    """One slash command. ``description_attr`` is a ``Texts`` field name."""

    command: str
    description_attr: str
    admin_only: bool = False


COMMANDS: tuple[CommandSpec, ...] = (
    CommandSpec("start", "CMD_START_DESC"),
    CommandSpec("help", "CMD_HELP_DESC"),
    CommandSpec("language", "CMD_LANGUAGE_DESC"),
    CommandSpec("list_codes", "CMD_LIST_CODES_DESC", admin_only=True),
    CommandSpec("delete_code", "CMD_DELETE_CODE_DESC", admin_only=True),
    CommandSpec("stats", "CMD_STATS_DESC", admin_only=True),
    CommandSpec("auditlog", "CMD_AUDITLOG_DESC", admin_only=True),
    CommandSpec("broadcast", "CMD_BROADCAST_DESC", admin_only=True),
    CommandSpec("cancel", "CMD_CANCEL_DESC", admin_only=True),
)


def user_specs() -> tuple[CommandSpec, ...]:
    """Commands visible to every user."""
    return tuple(spec for spec in COMMANDS if not spec.admin_only)


def admin_specs() -> tuple[CommandSpec, ...]:
    """Admin-only commands."""
    return tuple(spec for spec in COMMANDS if spec.admin_only)


def _description(texts: Texts, spec: CommandSpec) -> str:
    return str(getattr(texts, spec.description_attr))


def as_bot_commands(specs: tuple[CommandSpec, ...], texts: Texts) -> list[BotCommand]:
    """Convert specs to Telegram BotCommand objects."""
    return [
        BotCommand(command=spec.command, description=_description(texts, spec))
        for spec in specs
    ]


def format_help_text(texts: Texts, *, is_admin: bool) -> str:
    """Build /help body from the command registry for the current role."""
    lines = [texts.HELP_HEADER]
    for spec in user_specs():
        lines.append(f"/{spec.command} — {_description(texts, spec)}")
    if is_admin:
        lines.append("")
        lines.append(texts.HELP_ADMIN_HEADER)
        for spec in admin_specs():
            lines.append(f"/{spec.command} — {_description(texts, spec)}")
    return "\n".join(lines)
