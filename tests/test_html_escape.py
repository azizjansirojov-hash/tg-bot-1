"""Tests for HTML escaping helper."""

from __future__ import annotations

from bot.utils.html import escape_html


def test_escape_html_basic() -> None:
    assert escape_html("a < b & c > d") == "a &lt; b &amp; c &gt; d"


def test_escape_html_quotes_not_escaped() -> None:
    # quote=False — Telegram HTML templates do not use attributes here.
    assert '"' in escape_html('say "hi"')
    assert "'" in escape_html("it's")


def test_escape_html_preserves_plain() -> None:
    assert escape_html("Kino 102") == "Kino 102"
