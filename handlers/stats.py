"""Statistika va leaderboard."""
from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from db import Database, User
from keyboards import back_menu


router = Router(name="stats")


def _format_stats(user: User, quiz: dict) -> str:
    pct = (
        round(quiz["total_score"] * 100 / quiz["total_questions"])
        if quiz["total_questions"]
        else 0
    )
    return (
        "📊 *Sizning statistikangiz*\n\n"
        f"📈 Daraja: *{user.level}*\n"
        f"🌟 Umumiy ball: *{user.points}*\n"
        f"🔥 Ketma-ket kunlar: *{user.streak_days}*\n\n"
        "🎯 *Test natijalari:*\n"
        f"• Tugatilgan testlar: *{quiz['games']}*\n"
        f"• Umumiy to'g'ri javoblar: *{quiz['total_score']}/{quiz['total_questions']}* "
        f"({pct}%)\n\n"
        f"📅 Ro'yxatdan o'tgan: {user.created_at[:10]}"
    )


def _format_leaderboard(rows: list[tuple[str, int]]) -> str:
    if not rows:
        return "🏆 *Reyting*\n\nHali hech kim ball to'plamagan."
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 *Top 10 foydalanuvchi*\n"]
    for i, (name, points) in enumerate(rows):
        prefix = medals[i] if i < 3 else f"  {i + 1}."
        lines.append(f"{prefix} {name} — *{points}* ball")
    return "\n".join(lines)


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: Database, user: User) -> None:
    quiz = await db.quiz_summary(message.from_user.id)
    await message.answer(
        _format_stats(user, quiz),
        parse_mode="Markdown",
        reply_markup=back_menu(),
    )


@router.callback_query(F.data == "open:stats")
async def open_stats(callback: CallbackQuery, db: Database, user: User) -> None:
    quiz = await db.quiz_summary(callback.from_user.id)
    await callback.message.edit_text(
        _format_stats(user, quiz),
        parse_mode="Markdown",
        reply_markup=back_menu(),
    )
    await callback.answer()


@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message, db: Database) -> None:
    rows = await db.leaderboard(10)
    await message.answer(
        _format_leaderboard(rows),
        parse_mode="Markdown",
        reply_markup=back_menu(),
    )


@router.callback_query(F.data == "open:leaderboard")
async def open_leaderboard(callback: CallbackQuery, db: Database) -> None:
    rows = await db.leaderboard(10)
    await callback.message.edit_text(
        _format_leaderboard(rows),
        parse_mode="Markdown",
        reply_markup=back_menu(),
    )
    await callback.answer()
