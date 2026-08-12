"""HTML helpers for Telegram parse_mode=HTML messages."""

from __future__ import annotations

import html


def escape_html(text: str) -> str:
    """
    Escape user/admin-supplied text for Telegram HTML messages.

    Uses html.escape with quote=False (Telegram HTML does not use
    attribute contexts for our templates). Always call this before
    interpolating dynamic strings into parse_mode=HTML templates.
    """
    return html.escape(text, quote=False)
