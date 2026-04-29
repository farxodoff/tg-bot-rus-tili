"""Quiz (test) rejimi: 5 ta savol, ball, natija."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery

from ai_client import chat_json
from db import Database, User
from keyboards import quiz_finished, quiz_options, quiz_topics
from prompts import quiz_system
from states import (
    KEY_QUIZ_INDEX,
    KEY_QUIZ_QUESTIONS,
    KEY_QUIZ_SCORE,
    KEY_QUIZ_TOPIC,
    QuizState,
)

router = Router(name="quiz")
logger = logging.getLogger(__name__)


@router.callback_query(F.data == "open:quiz")
async def open_quiz(callback: CallbackQuery, state: FSMContext) -> None:
    await state.set_state(QuizState.choosing_topic)
    try:
        await callback.message.edit_text(
            "🎯 *Test rejimi.*\n\nMavzu tanlang:",
            parse_mode="Markdown",
            reply_markup=quiz_topics(),
        )
    except Exception:
        await callback.message.answer(
            "🎯 *Test rejimi.*\n\nMavzu tanlang:",
            parse_mode="Markdown",
            reply_markup=quiz_topics(),
        )
    await callback.answer()


@router.callback_query(QuizState.choosing_topic, F.data.startswith("qtopic:"))
async def on_topic(
    callback: CallbackQuery, state: FSMContext, user: User
) -> None:
    topic = callback.data.split(":", 1)[1]

    await callback.message.edit_text(
        f"⏳ Test tayyorlanmoqda... ({topic})",
        reply_markup=None,
    )
    await callback.answer()

    try:
        data = await chat_json(
            quiz_system(user.level, topic),
            "Generatsiya qiling.",
        )
        questions = _normalize_questions(data)
    except Exception:
        logger.exception("Quiz generatsiyasi xatosi")
        await callback.message.answer(
            "⚠️ Testni tayyorlab bo'lmadi. Qayta urinib ko'ring.",
            reply_markup=quiz_finished(),
        )
        return

    if not questions:
        await callback.message.answer(
            "⚠️ Savol topilmadi. Qayta urinib ko'ring.",
            reply_markup=quiz_finished(),
        )
        return

    await state.set_state(QuizState.answering)
    await state.update_data(
        {
            KEY_QUIZ_QUESTIONS: questions,
            KEY_QUIZ_INDEX: 0,
            KEY_QUIZ_SCORE: 0,
            KEY_QUIZ_TOPIC: topic,
        }
    )
    await _send_question(callback, state)


def _normalize_questions(data: dict) -> list[dict]:
    raw = data.get("questions") or data.get("items") or []
    cleaned = []
    for q in raw:
        question = q.get("question") or q.get("q")
        options = q.get("options") or q.get("variants") or []
        correct = q.get("correct")
        if isinstance(correct, str) and correct.isdigit():
            correct = int(correct)
        explanation = q.get("explanation") or q.get("explain") or ""
        if (
            question
            and isinstance(options, list)
            and len(options) == 4
            and isinstance(correct, int)
            and 0 <= correct < 4
        ):
            cleaned.append(
                {
                    "question": str(question),
                    "options": [str(o) for o in options],
                    "correct": correct,
                    "explanation": str(explanation),
                }
            )
        if len(cleaned) >= 5:
            break
    return cleaned


async def _send_question(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    questions: list[dict] = data[KEY_QUIZ_QUESTIONS]
    idx: int = data[KEY_QUIZ_INDEX]
    score: int = data[KEY_QUIZ_SCORE]

    q = questions[idx]
    text = (
        f"*Savol {idx + 1}/{len(questions)}* "
        f"(Ball: {score})\n\n"
        f"{q['question']}"
    )
    await callback.message.answer(
        text,
        parse_mode="Markdown",
        reply_markup=quiz_options(q["options"]),
    )


@router.callback_query(QuizState.answering, F.data.startswith("qans:"))
async def on_answer(
    callback: CallbackQuery, state: FSMContext, db: Database
) -> None:
    payload = callback.data.split(":", 1)[1]
    data = await state.get_data()

    if payload == "cancel":
        await state.clear()
        await callback.message.edit_text(
            "❌ Test bekor qilindi.", reply_markup=quiz_finished()
        )
        await callback.answer()
        return

    answer_idx = int(payload)
    questions: list[dict] = data[KEY_QUIZ_QUESTIONS]
    idx: int = data[KEY_QUIZ_INDEX]
    score: int = data[KEY_QUIZ_SCORE]
    topic: str = data[KEY_QUIZ_TOPIC]

    q = questions[idx]
    correct_idx = q["correct"]
    is_correct = answer_idx == correct_idx

    if is_correct:
        score += 1
        feedback = "✅ *To'g'ri!*"
    else:
        feedback = (
            f"❌ *Noto'g'ri.* To'g'ri javob: "
            f"*{chr(0x41 + correct_idx)}. {q['options'][correct_idx]}*"
        )

    if q["explanation"]:
        feedback += f"\n\n💡 {q['explanation']}"

    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        pass
    await callback.message.answer(feedback, parse_mode="Markdown")
    await callback.answer()

    idx += 1
    if idx >= len(questions):
        await db.save_quiz(callback.from_user.id, topic, score, len(questions))
        await db.add_points(callback.from_user.id, score * 5)
        await db.touch_streak(callback.from_user.id)
        await state.clear()

        verdict = _verdict(score, len(questions))
        await callback.message.answer(
            f"🏁 *Test tugadi!*\n\n"
            f"Natija: *{score}/{len(questions)}*\n"
            f"Mavzu: {topic}\n"
            f"+{score * 5} ball 🌟\n\n"
            f"{verdict}",
            parse_mode="Markdown",
            reply_markup=quiz_finished(),
        )
        return

    await state.update_data({KEY_QUIZ_INDEX: idx, KEY_QUIZ_SCORE: score})
    await _send_question(callback, state)


def _verdict(score: int, total: int) -> str:
    pct = score / total
    if pct == 1.0:
        return "🥇 Ajoyib! Mukammal natija."
    if pct >= 0.8:
        return "🥈 Juda yaxshi!"
    if pct >= 0.6:
        return "🥉 Yaxshi, davom eting."
    if pct >= 0.4:
        return "👍 Yomon emas, ko'proq mashq qiling."
    return "💪 Qoidalarni takrorlang va qayta urinib ko'ring."
