"""Locale package. Default language: Uzbek (Latin). Dict-of-classes by code."""

from __future__ import annotations

from bot.locales.en import Texts as EnglishTexts
from bot.locales.ru import Texts as RussianTexts
from bot.locales.uz import TEXTS, Texts

DEFAULT_LANGUAGE = "uz"
SUPPORTED_LANGUAGES: frozenset[str] = frozenset({"uz", "en", "ru"})

_TEXTS_BY_LANG: dict[str, Texts] = {
    "uz": TEXTS,
    "en": EnglishTexts(),
    "ru": RussianTexts(),
}


def normalize_language(code: str | None) -> str:
    """
    Map a Telegram language_code to a supported locale.

    ``en-US`` → ``en``, ``ru-RU`` → ``ru``, unknown or empty → default (``uz``).
    Never raises.
    """
    if not code or not isinstance(code, str):
        return DEFAULT_LANGUAGE
    primary = code.strip().replace("_", "-").split("-", 1)[0].lower()
    if primary in SUPPORTED_LANGUAGES:
        return primary
    return DEFAULT_LANGUAGE


def get_texts(code: str | None = None) -> Texts:
    """Return locale strings for ``code``, falling back to the default locale."""
    return _TEXTS_BY_LANG[normalize_language(code)]


__all__ = [
    "DEFAULT_LANGUAGE",
    "SUPPORTED_LANGUAGES",
    "TEXTS",
    "Texts",
    "get_texts",
    "normalize_language",
]
