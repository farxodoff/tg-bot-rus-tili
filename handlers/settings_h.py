"""Sozlamalar menyusi: daraja, kunlik so'z, tarixni tozalash."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from db import LEVELS, Database, User
from keyboards import level_picker, settings_menu

router = Router(name="settings")


@router.callback_query(F.data == "open:settings")
async def open_settings(callback: CallbackQuery, user: User) -> None:
    await _render_settings(callback, user)


async def _render_settings(callback: CallbackQuery, user: User) -> None:
    text = (
        "⚙️ <b>Sozlamalar</b>\n\n"
        f"📈 Daraja: <b>{user.level}</b>\n"
        f"🔔 Kunlik so'z: "
        f"<b>{'yoqilgan' if user.daily_enabled else 'oʻchirilgan'}</b>\n\n"
        "Quyidagi parametrlardan birini tanlang:"
    )
    markup = settings_menu(user.level, user.daily_enabled)
    try:
        await callback.message.edit_text(text, reply_markup=markup)
    except Exception:
        await callback.message.answer(text, reply_markup=markup)
    await callback.answer()


@router.callback_query(F.data == "settings:level")
async def settings_level(callback: CallbackQuery) -> None:
    await callback.message.edit_text(
        "📈 <b>Daraja tanlang:</b>\n\n"
        "• <b>A1</b> — boshlang'ich (alifbo, salomlashish)\n"
        "• <b>A2</b> — quyi-o'rta (kundalik mavzular)\n"
        "• <b>B1</b> — o'rta (mustaqil suhbat)\n"
        "• <b>B2</b> — yuqori-o'rta (murakkab gaplar)",
        reply_markup=level_picker(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("level:"))
async def set_level(
    callback: CallbackQuery, db: Database, user: User
) -> None:
    new_level = callback.data.split(":", 1)[1]
    if new_level not in LEVELS:
        await callback.answer("Noto'g'ri daraja", show_alert=True)
        return

    await db.set_level(callback.from_user.id, new_level)
    user.level = new_level
    await callback.answer(f"✅ Daraja: {new_level}")
    await _render_settings(callback, user)


@router.callback_query(F.data == "settings:daily")
async def toggle_daily(
    callback: CallbackQuery, db: Database, user: User
) -> None:
    new_value = not user.daily_enabled
    await db.set_daily_enabled(callback.from_user.id, new_value)
    user.daily_enabled = new_value
    await callback.answer(
        "✅ Kunlik so'z yoqildi" if new_value else "🔕 O'chirildi"
    )
    await _render_settings(callback, user)


@router.callback_query(F.data == "settings:reset")
async def reset_history(
    callback: CallbackQuery, db: Database, state: FSMContext
) -> None:
    await db.clear_history(callback.from_user.id)
    await state.clear()
    await callback.answer("🧹 Suhbat tarixi tozalandi", show_alert=True)
