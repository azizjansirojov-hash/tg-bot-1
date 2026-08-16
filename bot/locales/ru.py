"""Russian locale strings. Attribute names must match ``uz.Texts``."""

from __future__ import annotations

from bot.locales.uz import Texts as _BaseTexts


class Texts(_BaseTexts):
    """Russian overrides for all user-facing strings."""

    WELCOME = (
        "👋 Добро пожаловать!\n\n"
        "Отправьте код фильма — я пришлю соответствующее видео.\n\n"
        "Просто напишите число — вот и всё!"
    )
    GUIDANCE = (
        "Пожалуйста, отправьте код фильма только цифрами.\n"
        "Я понимаю только числовые коды."
    )
    CODE_NOT_FOUND = "Код не найден. Проверьте число и попробуйте снова."
    VIDEO_UNAVAILABLE = (
        "К сожалению, это видео сейчас недоступно. Попробуйте позже "
        "или напишите администратору."
    )
    GENERIC_ERROR = "Что-то пошло не так. Пожалуйста, попробуйте через минуту."
    ADMIN_ONLY = "Эта команда доступна только администраторам."
    RATE_LIMITED = (
        "Вы отправляете запросы слишком часто. Подождите около {seconds} "
        "секунд и попробуйте снова."
    )

    HELP_HEADER = "<b>Команды</b>"
    HELP_ADMIN_HEADER = "<b>Команды администратора</b>"
    CMD_START_DESC = "Кратко о боте"
    CMD_HELP_DESC = "Список доступных команд"
    CMD_LIST_CODES_DESC = "Список сохранённых кодов"
    CMD_DELETE_CODE_DESC = "Удалить код"
    CMD_STATS_DESC = "Статистика"
    CMD_AUDITLOG_DESC = "Журнал действий администратора"
    CMD_CANCEL_DESC = "Отменить текущее действие администратора"
    CMD_LANGUAGE_DESC = "Сменить язык"
    CMD_BROADCAST_DESC = "Отправить сообщение всем пользователям"

    LANGUAGE_CHOICE = "Выберите язык:"
    LANGUAGE_UPDATED = "Язык изменён на русский."
    START_LANGUAGE_PROMPT = (
        "Tilni tanlang / Выберите язык / Choose a language:"
    )
    BTN_LANG_UZ = "🇺🇿 O‘zbekcha"
    BTN_LANG_RU = "🇷🇺 Русский"
    BTN_LANG_EN = "🇬🇧 English"

    ADMIN_VIDEO_RECEIVED = (
        "Видео получено из канала-хранилища.\n\n"
        "Введите уникальный числовой код для этого видео "
        "(например: <b>102</b>)."
    )
    ADMIN_VIDEO_REJECTED_NOT_FORWARD = (
        "Видео не принято.\n\n"
        "Добавлять можно только видео, <b>пересланные из канала-хранилища</b>. "
        "Не отправляйте видео напрямую — сначала загрузите его в канал, "
        "затем перешлите боту."
    )
    ADMIN_VIDEO_REJECTED_WRONG_CHANNEL = (
        "Видео не принято.\n\n"
        "Это видео не из настроенного канала-хранилища. "
        "Пересылайте только из канала в <code>STORAGE_CHANNEL_ID</code>."
    )
    ADMIN_VIDEO_REJECTED_FROM_USER = (
        "Видео не принято.\n\n"
        "Видео, пересланные от пользователя, не принимаются. "
        "Перешлите видео из канала-хранилища."
    )
    ADMIN_CODE_DIGITS_ONLY = (
        "Код должен состоять только из цифр "
        "(например: <b>102</b>). Введите его снова."
    )
    ADMIN_CODE_EXISTS = (
        "Код <b>{code}</b> уже существует{title_part}.\n"
        "Заменить его новым видео?"
    )
    ADMIN_ASK_TITLE = (
        "Хорошо. Теперь отправьте название фильма или <b>-</b>, "
        "чтобы пропустить."
    )
    ADMIN_TITLE_TOO_LONG = (
        "Название слишком длинное (максимум {max_len} символов). "
        "Отправьте более короткое название или <b>-</b>, чтобы пропустить."
    )
    ADMIN_CONFIRM_SAVE = (
        "Подтвердите сохранение.\n\n"
        "<b>Код:</b> {code}\n"
        "<b>Название:</b> {title}\n\n"
        "Продолжить?"
    )
    ADMIN_SAVE_CANCELLED = "Сохранение отменено. Ничего не записано."
    ADMIN_OVERWRITE_CANCELLED = (
        "Отменено. Код <b>{code}</b> не изменён."
    )
    ADMIN_OVERWRITE_CONFIRMED = (
        "Замена <b>{code}</b> подтверждена.\n"
        "Теперь отправьте название или <b>-</b>, чтобы пропустить."
    )
    ADMIN_SESSION_ERROR = (
        "Произошла ошибка сессии. Перешлите видео ещё раз."
    )
    ADMIN_SAVE_FAILED = "Не удалось сохранить. Попробуйте снова."
    ADMIN_SAVE_SUCCESS = (
        "✅ Фильм успешно сохранён!\n\n"
        "<b>Код:</b> {code}\n"
        "<b>Название:</b> {title}\n"
        "<b>ID сообщения в канале:</b> {channel_message_id}"
    )
    ADMIN_TITLE_NONE = "(нет)"
    ADMIN_FSM_CANCELLED = "Отменено. Ничего не сохранено."
    ADMIN_INVALID_ACTION = "Недопустимое действие."

    ADMIN_LIST_EMPTY = "Пока нет сохранённых фильмов."
    ADMIN_LIST_HEADER = (
        "<b>Сохранённые коды</b> "
        "(страница {page}/{total_pages}, всего {total}):\n"
    )
    ADMIN_LIST_ITEM = "• <code>{code}</code> — {title}"
    ADMIN_DELETE_USAGE = "Использование: <code>/delete_code 102</code>"
    ADMIN_DELETE_NOT_FOUND = "Код <b>{code}</b> не найден."
    ADMIN_DELETE_CONFIRM = (
        "Удалить код <b>{code}</b> ({title})?\n"
        "Это действие нельзя отменить."
    )
    ADMIN_DELETE_CANCELLED = (
        "Удаление отменено. Код <b>{code}</b> сохранён."
    )
    ADMIN_DELETE_SUCCESS = "🗑 Код <b>{code}</b> удалён."
    ADMIN_DELETE_ALREADY_GONE = (
        "Код <b>{code}</b> не найден (возможно, он уже удалён)."
    )
    ADMIN_STATS = (
        "📊 <b>Статистика</b>\n\n"
        "Сохранённые фильмы: <b>{movies}</b>\n"
        "Пользователи, запросившие код: <b>{users}</b>"
    )
    ADMIN_INVALID_PAGE = "Неверная страница."
    ADMIN_AUDIT_EMPTY = "Журнал действий пуст."
    ADMIN_AUDIT_HEADER = (
        "<b>Журнал действий администратора</b> "
        "(страница {page}/{total_pages}, всего {total}):\n"
    )
    ADMIN_AUDIT_ITEM = (
        "• <code>{timestamp}</code> | admin=<code>{admin_id}</code> | "
        "<b>{action}</b> | target=<code>{target}</code>"
    )

    BTN_PREV = "« Назад"
    BTN_NEXT = "Вперёд »"
    BTN_OVERWRITE_YES = "Да, заменить"
    BTN_OVERWRITE_NO = "Отмена"
    BTN_DELETE_YES = "Да, удалить"
    BTN_DELETE_NO = "Нет, отмена"
    BTN_SAVE_YES = "Да, сохранить"
    BTN_SAVE_NO = "Нет, отмена"
    BTN_BROADCAST_YES = "Да, отправить"
    BTN_BROADCAST_NO = "Нет, отмена"

    ADMIN_BROADCAST_ASK = (
        "Отправьте текст сообщения (только обычный текст).\n"
        "Отмена: /cancel"
    )
    ADMIN_BROADCAST_EMPTY = "Нет активных пользователей для рассылки."
    ADMIN_BROADCAST_CONFIRM = (
        "Сообщение будет отправлено <b>{count}</b> пользователям. Подтвердить?"
    )
    ADMIN_BROADCAST_CANCELLED = (
        "Рассылка отменена. Никому ничего не отправлено."
    )
    ADMIN_BROADCAST_TEXT_TOO_LONG = (
        "Текст слишком длинный (максимум {max_len} символов). "
        "Отправьте более короткий текст."
    )
    ADMIN_BROADCAST_NEED_TEXT = (
        "Пожалуйста, отправьте текст (пустые сообщения не принимаются)."
    )
    ADMIN_BROADCAST_SUMMARY = (
        "📣 <b>Рассылка завершена</b>\n\n"
        "Попыток: <b>{attempted}</b>\n"
        "Успешно: <b>{succeeded}</b>\n"
        "Заблокировали бота: <b>{failed_blocked}</b>\n"
        "Другие ошибки: <b>{failed_other}</b>\n"
        "Длительность: <b>{duration_ms}</b> мс"
    )


TEXTS = Texts()
