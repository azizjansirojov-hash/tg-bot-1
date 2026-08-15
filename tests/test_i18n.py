"""Locale lookup, language defaults, and /language persistence."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from bot.handlers import user as user_handlers
from bot.keyboards.inline import language_keyboard
from bot.locales import DEFAULT_LANGUAGE, TEXTS, get_texts, normalize_language
from bot.locales.en import TEXTS as EN_TEXTS
from bot.locales.ru import TEXTS as RU_TEXTS
from bot.locales.uz import Texts as UzTexts


def _lang_callback_data(markup: object) -> list[str]:
    rows = getattr(markup, "inline_keyboard", [])
    return [btn.callback_data for row in rows for btn in row]


def test_normalize_unknown_falls_back_to_uz() -> None:
    assert normalize_language("fr") == DEFAULT_LANGUAGE
    assert normalize_language("xx") == DEFAULT_LANGUAGE
    assert normalize_language(None) == DEFAULT_LANGUAGE
    assert normalize_language("") == DEFAULT_LANGUAGE


def test_normalize_primary_subtag() -> None:
    assert normalize_language("en-US") == "en"
    assert normalize_language("uz-UZ") == "uz"
    assert normalize_language("en") == "en"
    assert normalize_language("ru") == "ru"
    assert normalize_language("ru-RU") == "ru"


def test_get_texts_unsupported_returns_uzbek_not_placeholder() -> None:
    texts = get_texts("fr")
    assert texts.WELCOME == TEXTS.WELCOME
    assert "{missing" not in texts.WELCOME
    assert texts.HELP_HEADER == TEXTS.HELP_HEADER


def test_get_texts_english() -> None:
    texts = get_texts("en")
    assert texts.WELCOME == EN_TEXTS.WELCOME
    assert texts.WELCOME != TEXTS.WELCOME


def test_get_texts_russian() -> None:
    texts = get_texts("ru")
    assert texts.WELCOME == RU_TEXTS.WELCOME
    assert texts.WELCOME != TEXTS.WELCOME
    assert texts.WELCOME != EN_TEXTS.WELCOME


def test_locale_classes_share_the_same_fields() -> None:
    base = {
        name
        for name, value in vars(UzTexts).items()
        if name.isupper() and isinstance(value, str)
    }
    for locale in (EN_TEXTS, RU_TEXTS, TEXTS):
        present = {
            name
            for name, value in vars(type(locale)).items()
            if name.isupper() and isinstance(value, str)
        }
        assert base <= present


def test_language_keyboard_includes_russian() -> None:
    datas = _lang_callback_data(language_keyboard())
    assert datas == ["lang:uz", "lang:ru", "lang:en"]


@pytest.mark.asyncio
async def test_cmd_start_new_user_shows_picker_not_welcome(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=55, language_code="en")
    session = AsyncMock()
    ensure = AsyncMock()
    get_lang = AsyncMock(return_value=None)
    monkeypatch.setattr(user_handlers.crud, "ensure_user", ensure)
    monkeypatch.setattr(user_handlers.crud, "get_user_language", get_lang)
    safe = AsyncMock()
    monkeypatch.setattr(user_handlers, "safe_answer", safe)

    await user_handlers.cmd_start(message, texts=get_texts("en"), session=session)

    ensure.assert_not_awaited()
    args, kwargs = safe.await_args
    assert args[1] == EN_TEXTS.START_LANGUAGE_PROMPT
    assert args[1] != EN_TEXTS.WELCOME
    markup = kwargs.get("reply_markup")
    assert _lang_callback_data(markup) == ["lang:uz", "lang:ru", "lang:en"]


@pytest.mark.asyncio
async def test_cmd_start_new_user_unsupported_telegram_lang_still_picker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=56, language_code="fr")
    session = AsyncMock()
    ensure = AsyncMock()
    monkeypatch.setattr(user_handlers.crud, "ensure_user", ensure)
    monkeypatch.setattr(
        user_handlers.crud, "get_user_language", AsyncMock(return_value=None)
    )
    safe = AsyncMock()
    monkeypatch.setattr(user_handlers, "safe_answer", safe)

    await user_handlers.cmd_start(message, texts=get_texts("fr"), session=session)

    ensure.assert_not_awaited()
    assert safe.await_args.args[1] == TEXTS.START_LANGUAGE_PROMPT


@pytest.mark.asyncio
async def test_cmd_start_returning_user_skips_picker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=55, language_code="en")
    session = AsyncMock()
    ensure = AsyncMock()
    monkeypatch.setattr(user_handlers.crud, "ensure_user", ensure)
    monkeypatch.setattr(
        user_handlers.crud, "get_user_language", AsyncMock(return_value="en")
    )
    safe = AsyncMock()
    monkeypatch.setattr(user_handlers, "safe_answer", safe)

    await user_handlers.cmd_start(message, texts=get_texts("en"), session=session)

    ensure.assert_awaited_with(session, 55, "en")
    args, _kwargs = safe.await_args
    assert args[1] == EN_TEXTS.WELCOME


@pytest.mark.asyncio
async def test_language_callback_persists_choice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    callback = MagicMock()
    callback.data = "lang:en"
    callback.from_user = MagicMock(id=77)
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    session = AsyncMock()
    set_lang = AsyncMock()
    monkeypatch.setattr(user_handlers.crud, "set_user_language", set_lang)
    monkeypatch.setattr(
        user_handlers.crud, "get_user_language", AsyncMock(return_value="uz")
    )
    safe = AsyncMock()
    monkeypatch.setattr(user_handlers, "safe_answer", safe)

    await user_handlers.language_chosen(callback, session)

    set_lang.assert_awaited_with(session, 77, "en")
    args, _kwargs = callback.message.edit_text.await_args
    assert args[0] == EN_TEXTS.LANGUAGE_UPDATED
    safe.assert_not_awaited()


@pytest.mark.asyncio
async def test_language_callback_russian_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    callback = MagicMock()
    callback.data = "lang:ru"
    callback.from_user = MagicMock(id=78)
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    session = AsyncMock()
    monkeypatch.setattr(user_handlers.crud, "set_user_language", AsyncMock())
    monkeypatch.setattr(
        user_handlers.crud, "get_user_language", AsyncMock(return_value="en")
    )
    monkeypatch.setattr(user_handlers, "safe_answer", AsyncMock())

    await user_handlers.language_chosen(callback, session)

    args, _kwargs = callback.message.edit_text.await_args
    assert args[0] == RU_TEXTS.LANGUAGE_UPDATED


@pytest.mark.asyncio
async def test_first_start_picker_then_welcome_in_chosen_language(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    callback = MagicMock()
    callback.data = "lang:ru"
    callback.from_user = MagicMock(id=80)
    callback.message = MagicMock()
    callback.message.edit_text = AsyncMock()
    callback.answer = AsyncMock()
    session = AsyncMock()
    set_lang = AsyncMock()
    monkeypatch.setattr(user_handlers.crud, "set_user_language", set_lang)
    monkeypatch.setattr(
        user_handlers.crud, "get_user_language", AsyncMock(return_value=None)
    )
    safe = AsyncMock()
    monkeypatch.setattr(user_handlers, "safe_answer", safe)

    await user_handlers.language_chosen(callback, session)

    set_lang.assert_awaited_with(session, 80, "ru")
    assert callback.message.edit_text.await_args.args[0] == RU_TEXTS.LANGUAGE_UPDATED
    assert safe.await_args.args[1] == RU_TEXTS.WELCOME


@pytest.mark.asyncio
async def test_language_command_still_works_after_first_start_picker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After the one-time /start picker, /language can change locale again."""
    session = AsyncMock()
    set_lang = AsyncMock()
    get_lang = AsyncMock(side_effect=[None, "ru"])
    monkeypatch.setattr(user_handlers.crud, "set_user_language", set_lang)
    monkeypatch.setattr(user_handlers.crud, "get_user_language", get_lang)
    safe = AsyncMock()
    monkeypatch.setattr(user_handlers, "safe_answer", safe)

    first = MagicMock()
    first.data = "lang:ru"
    first.from_user = MagicMock(id=81)
    first.message = MagicMock()
    first.message.edit_text = AsyncMock()
    first.answer = AsyncMock()
    await user_handlers.language_chosen(first, session)
    assert set_lang.await_args.args == (session, 81, "ru")
    assert safe.await_args.args[1] == RU_TEXTS.WELCOME

    lang_msg = MagicMock()
    lang_msg.from_user = MagicMock(id=81, language_code="ru")
    monkeypatch.setattr(user_handlers.crud, "ensure_user", AsyncMock())
    await user_handlers.cmd_language(lang_msg, texts=get_texts("ru"), session=session)
    choice_args, choice_kwargs = safe.await_args
    assert choice_args[1] == RU_TEXTS.LANGUAGE_CHOICE
    assert _lang_callback_data(choice_kwargs.get("reply_markup")) == [
        "lang:uz",
        "lang:ru",
        "lang:en",
    ]

    later = MagicMock()
    later.data = "lang:en"
    later.from_user = MagicMock(id=81)
    later.message = MagicMock()
    later.message.edit_text = AsyncMock()
    later.answer = AsyncMock()
    await user_handlers.language_chosen(later, session)
    assert set_lang.await_args.args == (session, 81, "en")
    assert later.message.edit_text.await_args.args[0] == EN_TEXTS.LANGUAGE_UPDATED
    assert set_lang.await_count == 2


@pytest.mark.asyncio
async def test_cmd_language_shows_russian_button(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=90, language_code="uz")
    monkeypatch.setattr(user_handlers.crud, "ensure_user", AsyncMock())
    safe = AsyncMock()
    monkeypatch.setattr(user_handlers, "safe_answer", safe)

    await user_handlers.cmd_language(message, texts=TEXTS)

    markup = safe.await_args.kwargs.get("reply_markup")
    assert "lang:ru" in _lang_callback_data(markup)


@pytest.mark.asyncio
async def test_help_follows_english_texts(monkeypatch: pytest.MonkeyPatch) -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=999)
    safe = AsyncMock()
    monkeypatch.setattr(user_handlers, "safe_answer", safe)

    await user_handlers.cmd_help(message, texts=get_texts("en"))

    body = safe.await_args.args[1]
    assert EN_TEXTS.HELP_HEADER in body
    assert TEXTS.HELP_HEADER not in body
    assert "/language" in body


@pytest.mark.asyncio
async def test_help_follows_russian_texts(monkeypatch: pytest.MonkeyPatch) -> None:
    message = MagicMock()
    message.from_user = MagicMock(id=1001)
    safe = AsyncMock()
    monkeypatch.setattr(user_handlers, "safe_answer", safe)

    await user_handlers.cmd_help(message, texts=get_texts("ru"))

    body = safe.await_args.args[1]
    assert RU_TEXTS.HELP_HEADER in body
    assert TEXTS.HELP_HEADER not in body
    assert EN_TEXTS.HELP_HEADER not in body


@pytest.mark.asyncio
async def test_guidance_follows_russian_texts(monkeypatch: pytest.MonkeyPatch) -> None:
    message = MagicMock()
    safe = AsyncMock()
    monkeypatch.setattr(user_handlers, "safe_answer", safe)

    await user_handlers.handle_non_numeric_text(message, texts=get_texts("ru"))

    assert safe.await_args.args[1] == RU_TEXTS.GUIDANCE
