"""Asosiy buyruqlar (/start, /menu, /help, /reset) va asosiy menyu callbacklari."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from db import Database
from keyboards import main_menu

router = Router(name="common")


WELCOME_TEXT = (
    "Salom! 👋\n\n"
    "Men sizga <b>rus tilini o'rgatuvchi</b> botman. Quyidagi rejimlardan birini tanlang:\n\n"
    "📚 <b>Grammatika</b> — qoidalar va misollar\n"
    "💬 <b>So'z boyligi</b> — yangi so'zlar va iboralar\n"
    "❓ <b>Savol-javob</b> — kundalik suhbat shablonlari\n"
    "🔄 <b>Tarjima</b> — o'zbekcha ↔ ruscha\n"
    "🗣 <b>Dialog</b> — men bilan ruscha suhbatlashing\n"
    "📝 <b>Matn tahlili</b> — ruscha matnni tahlil qilish\n"
    "🎯 <b>Test</b> — bilimingizni sinab ko'ring\n\n"
    "🔊 Ovozli xabar yuborsangiz — sizni eshitib, ruscha matnga aylantirib beraman.\n"
    "🎧 Bot javoblarini eshitish uchun har xabar ostidagi <b>🔊 Eshitish</b> tugmasini bosing.\n\n"
    "/menu — istalgan paytda asosiy menyu\n"
    "/help — yordam"
)


HELP_TEXT = (
    "<b>Buyruqlar:</b>\n"
    "/start — botni qayta ishga tushirish\n"
    "/menu — asosiy menyu\n"
    "/stats — sizning statistikangiz\n"
    "/leaderboard — top 10 foydalanuvchi\n"
    "/reset — joriy rejim suhbat tarixini tozalash\n"
    "/cancel — joriy amalni bekor qilish\n"
    "/help — yordam\n\n"
    "<b>Maslahat:</b> ovozli xabar yuborib, ruscha gapirib mashq qiling. "
    "Bot sizni AI orqali tushunadi va to'g'ri javob beradi."
)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, db: Database) -> None:
    await state.clear()
    await db.touch_streak(message.from_user.id)
    await message.answer(WELCOME_TEXT, reply_markup=main_menu())


@router.message(Command("menu"))
async def cmd_menu(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Asosiy menyu. Rejim tanlang:", reply_markup=main_menu())


@router.message(Command("help"))
async def cmd_help(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("✅ Bekor qilindi.", reply_markup=main_menu())


@router.message(Command("reset"))
async def cmd_reset(message: Message, db: Database, state: FSMContext) -> None:
    await db.clear_history(message.from_user.id)
    await state.clear()
    await message.answer("🧹 Suhbat tarixi tozalandi.", reply_markup=main_menu())


@router.callback_query(F.data == "open:menu")
async def open_menu(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    try:
        await callback.message.edit_text(
            "Asosiy menyu. Rejim tanlang:",
            reply_markup=main_menu(),
        )
    except Exception:
        await callback.message.answer(
            "Asosiy menyu. Rejim tanlang:",
            reply_markup=main_menu(),
        )
    await callback.answer()
