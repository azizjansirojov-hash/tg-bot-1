"""
Centralized user-facing and admin-facing bot texts.

Default locale is Uzbek (Latin). Add sibling modules (e.g. `en.py`) later and
switch the import in `bot/locales/__init__.py` for multi-language support.
"""

from __future__ import annotations


class Texts:
    """Named message templates. Use `.format(...)` for placeholders."""

    # --- User ---
    WELCOME = (
        "👋 Xush kelibsiz!\n\n"
        "Kino kodini yuboring — men sizga mos "
        "videoni yuboraman.\n\n"
        "Faqat raqamni yozib, yuboring — shu qadar oddiy!"
    )
    GUIDANCE = (
        "Iltimos, kino kodini raqam ko‘rinishida yuboring. "
        "\n"
        "Men faqat raqamli kodlarni tushunaman."
    )
    CODE_NOT_FOUND = "Kod topilmadi. Raqamni tekshirib, qayta urinib ko‘ring."
    VIDEO_UNAVAILABLE = (
        "Kechirasiz, bu video hozircha mavjud emas. Keyinroq urinib ko‘ring "
        "yoki admin bilan bog‘laning."
    )
    GENERIC_ERROR = "Nimadir xato ketdi. Birozdan so‘ng qayta urinib ko‘ring."
    ADMIN_ONLY = "Bu buyruq faqat adminlar uchun."
    RATE_LIMITED = (
        "Juda tez-tez so‘rov yuboryapsiz. Taxminan {seconds} soniya kutib, "
        "qayta urinib ko‘ring."
    )

    # --- Admin: add-movie FSM ---
    ADMIN_VIDEO_RECEIVED = (
        "Video ombor kanalidan qabul qilindi.\n\n"
        "Shu video uchun unikal raqamli kod kiriting (masalan: <b>102</b>)."
    )
    ADMIN_VIDEO_REJECTED_NOT_FORWARD = (
        "Video qabul qilinmadi.\n\n"
        "Faqat <b>ombor kanalidan</b> forward qilingan videolar qo‘shiladi. "
        "Videoni to‘g‘ridan-to‘g‘ri yubormang — avval ombor kanaliga joylang, "
        "so‘ng botga forward qiling."
    )
    ADMIN_VIDEO_REJECTED_WRONG_CHANNEL = (
        "Video qabul qilinmadi.\n\n"
        "Bu video sozlangan ombor kanalidan emas. "
        "Faqat <code>STORAGE_CHANNEL_ID</code> dagi kanaldan forward qiling."
    )
    ADMIN_VIDEO_REJECTED_FROM_USER = (
        "Video qabul qilinmadi.\n\n"
        "Foydalanuvchidan forward qilingan videolar qabul qilinmaydi. "
        "Videoni ombor kanalidan forward qiling."
    )
    ADMIN_CODE_DIGITS_ONLY = (
        "Kod faqat raqamlardan iborat bo‘lishi kerak "
        "(masalan: <b>102</b>). Qayta kiriting."
    )
    ADMIN_CODE_EXISTS = (
        "Kod <b>{code}</b> allaqachon mavjud{title_part}.\n"
        "Yangi video bilan almashtirilsinmi?"
    )
    ADMIN_ASK_TITLE = (
        "Yaxshi. Endi film nomini yuboring yoki o‘tkazib yuborish uchun "
        "<b>-</b> yuboring."
    )
    ADMIN_TITLE_TOO_LONG = (
        "Nom juda uzun (maksimum {max_len} belgi). "
        "Qisqaroq nom yuboring yoki o‘tkazib yuborish uchun <b>-</b> yuboring."
    )
    ADMIN_CONFIRM_SAVE = (
        "Saqlashni tasdiqlang.\n\n"
        "<b>Kod:</b> {code}\n"
        "<b>Nomi:</b> {title}\n\n"
        "Davom etilsinmi?"
    )
    ADMIN_SAVE_CANCELLED = "Saqlash bekor qilindi. Hech narsa yozilmadi."
    ADMIN_OVERWRITE_CANCELLED = (
        "Bekor qilindi. <b>{code}</b> kodi o‘zgartirilmadi."
    )
    ADMIN_OVERWRITE_CONFIRMED = (
        "<b>{code}</b> kodi almashtirish uchun tasdiqlandi.\n"
        "Endi nom yuboring yoki o‘tkazib yuborish uchun <b>-</b> yuboring."
    )
    ADMIN_SESSION_ERROR = (
        "Sessiya bilan bog‘liq xatolik yuz berdi. "
        "Videoni qaytadan forward qiling."
    )
    ADMIN_SAVE_FAILED = "Saqlash amalga oshmadi. Qayta urinib ko‘ring."
    ADMIN_SAVE_SUCCESS = (
        "✅ Film muvaffaqiyatli saqlandi!\n\n"
        "<b>Kod:</b> {code}\n"
        "<b>Nomi:</b> {title}\n"
        "<b>Kanal xabar ID:</b> {channel_message_id}"
    )
    ADMIN_TITLE_NONE = "(yo‘q)"
    ADMIN_FSM_CANCELLED = "Bekor qilindi. Hech narsa saqlanmadi."
    ADMIN_INVALID_ACTION = "Noto‘g‘ri amal."

    # --- Admin: list / delete / stats / audit ---
    ADMIN_LIST_EMPTY = "Hali hech qanday film saqlanmagan."
    ADMIN_LIST_HEADER = (
        "<b>Saqlangan kodlar</b> "
        "(sahifa {page}/{total_pages}, jami {total}):\n"
    )
    ADMIN_LIST_ITEM = "• <code>{code}</code> — {title}"
    ADMIN_DELETE_USAGE = "Foydalanish: <code>/delete_code 102</code>"
    ADMIN_DELETE_NOT_FOUND = "<b>{code}</b> kodi topilmadi."
    ADMIN_DELETE_CONFIRM = (
        "<b>{code}</b> ({title}) kodi o‘chirilsinmi?\n"
        "Bu amalni qaytarib bo‘lmaydi."
    )
    ADMIN_DELETE_CANCELLED = (
        "O‘chirish bekor qilindi. <b>{code}</b> kodi saqlanib qoldi."
    )
    ADMIN_DELETE_SUCCESS = "🗑 <b>{code}</b> kodi o‘chirildi."
    ADMIN_DELETE_ALREADY_GONE = (
        "<b>{code}</b> kodi topilmadi (allaqachon o‘chirilgan bo‘lishi mumkin)."
    )
    ADMIN_STATS = (
        "📊 <b>Statistika</b>\n\n"
        "Saqlangan filmlar: <b>{movies}</b>\n"
        "Kod so‘ragan foydalanuvchilar: <b>{users}</b>"
    )
    ADMIN_INVALID_PAGE = "Noto‘g‘ri sahifa."
    ADMIN_AUDIT_EMPTY = "Audit jurnalida hali yozuv yo‘q."
    ADMIN_AUDIT_HEADER = (
        "<b>Admin audit jurnali</b> "
        "(sahifa {page}/{total_pages}, jami {total}):\n"
    )
    ADMIN_AUDIT_ITEM = (
        "• <code>{timestamp}</code> | admin=<code>{admin_id}</code> | "
        "<b>{action}</b> | target=<code>{target}</code>"
    )

    # --- Button labels ---
    BTN_PREV = "« Oldingi"
    BTN_NEXT = "Keyingi »"
    BTN_OVERWRITE_YES = "Ha, almashtirish"
    BTN_OVERWRITE_NO = "Bekor qilish"
    BTN_DELETE_YES = "Ha, o‘chirilsin"
    BTN_DELETE_NO = "Yo‘q, bekor"
    BTN_SAVE_YES = "Ha, saqlash"
    BTN_SAVE_NO = "Yo‘q, bekor"


TEXTS = Texts()
