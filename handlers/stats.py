"""Statistika va leaderboard."""
from __future__ import annotations

import html

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
        "📊 <b>Sizning statistikangiz</b>\n\n"
        f"📈 Daraja: <b>{user.level}</b>\n"
        f"🌟 Umumiy ball: <b>{user.points}</b>\n"
        f"🔥 Ketma-ket kunlar: <b>{user.streak_days}</b>\n\n"
        "🎯 <b>Test natijalari:</b>\n"
        f"• Tugatilgan testlar: <b>{quiz['games']}</b>\n"
        f"• Umumiy to'g'ri javoblar: <b>{quiz['total_score']}/{quiz['total_questions']}</b> "
        f"({pct}%)\n\n"
        f"📅 Ro'yxatdan o'tgan: {user.created_at[:10]}"
    )


def _format_leaderboard(rows: list[tuple[str, int]]) -> str:
    if not rows:
        return "🏆 <b>Reyting</b>\n\nHali hech kim ball to'plamagan."
    medals = ["🥇", "🥈", "🥉"]
    lines = ["🏆 <b>Top 10 foydalanuvchi</b>\n"]
    for i, (name, points) in enumerate(rows):
        prefix = medals[i] if i < 3 else f"  {i + 1}."
        lines.append(f"{prefix} {html.escape(name)} — <b>{points}</b> ball")
    return "\n".join(lines)


@router.message(Command("stats"))
async def cmd_stats(message: Message, db: Database, user: User) -> None:
    quiz = await db.quiz_summary(message.from_user.id)
    await message.answer(_format_stats(user, quiz), reply_markup=back_menu())


@router.callback_query(F.data == "open:stats")
async def open_stats(callback: CallbackQuery, db: Database, user: User) -> None:
    quiz = await db.quiz_summary(callback.from_user.id)
    await callback.message.edit_text(
        _format_stats(user, quiz), reply_markup=back_menu()
    )
    await callback.answer()


@router.message(Command("leaderboard"))
async def cmd_leaderboard(message: Message, db: Database) -> None:
    rows = await db.leaderboard(10)
    await message.answer(_format_leaderboard(rows), reply_markup=back_menu())


@router.callback_query(F.data == "open:leaderboard")
async def open_leaderboard(callback: CallbackQuery, db: Database) -> None:
    rows = await db.leaderboard(10)
    await callback.message.edit_text(
        _format_leaderboard(rows), reply_markup=back_menu()
    )
    await callback.answer()
