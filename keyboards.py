"""Inline va reply klaviaturalar."""
from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from db import LEVELS
from prompts import MODE_TITLES


# ---- Asosiy menyu ----
def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for mode, title in MODE_TITLES.items():
        builder.button(text=title, callback_data=f"mode:{mode}")
    builder.button(text="🎯 Test (Quiz)", callback_data="open:quiz")
    builder.button(text="📊 Statistika", callback_data="open:stats")
    builder.button(text="⚙️ Sozlamalar", callback_data="open:settings")
    builder.button(text="🏆 Reyting", callback_data="open:leaderboard")
    builder.adjust(2, 2, 2, 2, 2)
    return builder.as_markup()


def back_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="open:menu")]
        ]
    )


def reply_actions() -> InlineKeyboardMarkup:
    """Bot javobi ostida — eshitish va menyu tugmalari."""
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔊 Eshitish", callback_data="tts")],
            [InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="open:menu")],
        ]
    )


# ---- Sozlamalar ----
def settings_menu(level: str, daily_enabled: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text=f"📈 Daraja: {level}", callback_data="settings:level")
    daily_label = "yoqilgan ✅" if daily_enabled else "oʻchirilgan ❌"
    builder.button(
        text=f"🔔 Kunlik so'z: {daily_label}",
        callback_data="settings:daily",
    )
    builder.button(text="🧹 Tarixni tozalash", callback_data="settings:reset")
    builder.button(text="⬅️ Orqaga", callback_data="open:menu")
    builder.adjust(1)
    return builder.as_markup()


def level_picker() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for lvl in LEVELS:
        builder.button(text=lvl, callback_data=f"level:{lvl}")
    builder.button(text="⬅️ Orqaga", callback_data="open:settings")
    builder.adjust(4, 1)
    return builder.as_markup()


# ---- Quiz ----
QUIZ_TOPICS = [
    ("Salomlashish", "salomlashish"),
    ("Sonlar", "sonlar"),
    ("Oila", "oila"),
    ("Oziq-ovqat", "oziq-ovqat"),
    ("Sayohat", "sayohat"),
    ("Fe'l zamonlari", "fe'l zamonlari"),
    ("Kelishiklar", "kelishiklar"),
    ("Aralash mavzular", "aralash"),
]


def quiz_topics() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for label, value in QUIZ_TOPICS:
        builder.button(text=label, callback_data=f"qtopic:{value}")
    builder.button(text="⬅️ Asosiy menyu", callback_data="open:menu")
    builder.adjust(2, 2, 2, 2, 1)
    return builder.as_markup()


def quiz_options(options: list[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for idx, opt in enumerate(options):
        label = f"{chr(0x41 + idx)}. {opt}"
        if len(label) > 64:
            label = label[:61] + "..."
        builder.button(text=label, callback_data=f"qans:{idx}")
    builder.button(text="❌ Testni to'xtatish", callback_data="qans:cancel")
    builder.adjust(1)
    return builder.as_markup()


def quiz_finished() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔁 Yana", callback_data="open:quiz")],
            [InlineKeyboardButton(text="⬅️ Asosiy menyu", callback_data="open:menu")],
        ]
    )
