"""6 ta o'rganish rejimi: chat handler + TTS tugmasi."""
from __future__ import annotations

import logging
from io import BytesIO

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from ai_client import chat, extract_russian, has_russian, text_to_speech
from db import Database, User
from keyboards import back_menu, reply_actions
from prompts import DIALOG_OPENER, MODE_INTROS, MODE_TITLES, mode_prompt
from states import KEY_MODE, ModeState

router = Router(name="modes")
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("mode:"))
async def on_mode_pick(
    callback: CallbackQuery, state: FSMContext, db: Database, user: User
) -> None:
    mode = callback.data.split(":", 1)[1]
    if mode not in MODE_INTROS:
        await callback.answer("Noma'lum rejim", show_alert=True)
        return

    await state.set_state(ModeState.chatting)
    await state.update_data({KEY_MODE: mode})
    await db.clear_history(callback.from_user.id, mode)

    intro = MODE_INTROS[mode]
    try:
        await callback.message.edit_text(
            f"{MODE_TITLES[mode]}\n\n{intro}",
            parse_mode="Markdown",
            reply_markup=back_menu(),
        )
    except Exception:
        await callback.message.answer(
            f"{MODE_TITLES[mode]}\n\n{intro}",
            parse_mode="Markdown",
            reply_markup=back_menu(),
        )

    if mode == "dialog":
        await callback.message.answer(DIALOG_OPENER)
        await db.add_message(
            callback.from_user.id, mode, "assistant", DIALOG_OPENER
        )

    await callback.answer()


@router.message(ModeState.chatting, F.text)
async def on_chat_message(
    message: Message, state: FSMContext, db: Database, user: User
) -> None:
    data = await state.get_data()
    mode = data.get(KEY_MODE)
    if not mode:
        await message.answer("Avval rejim tanlang.", reply_markup=back_menu())
        return

    user_id = message.from_user.id
    history = await db.history(user_id, mode, limit=12)
    system = mode_prompt(mode, user.level)

    await message.bot.send_chat_action(message.chat.id, "typing")

    try:
        reply = await chat(system, history, message.text)
    except Exception:
        logger.exception("AI chat xatosi")
        await message.answer(
            "⚠️ Hozir javob bera olmadim. Biroz keyinroq qayta urinib ko'ring."
        )
        return

    await db.add_message(user_id, mode, "user", message.text)
    msg = await message.answer(reply)
    await db.add_message(user_id, mode, "assistant", reply)
    await msg.edit_reply_markup(reply_markup=reply_actions(message_idx=msg.message_id))

    await db.add_points(user_id, 1)
    await db.touch_streak(user_id)


@router.callback_query(F.data.startswith("tts:"))
async def on_tts(callback: CallbackQuery) -> None:
    """Avvalgi xabarning ruscha qismini ovoz qilib yuboradi."""
    if not callback.message or not callback.message.reply_to_message:
        # bot javobining matni — `callback.message` o'zining matnida
        text = callback.message.text or callback.message.caption or ""
    else:
        text = callback.message.text or ""

    if not text or not has_russian(text):
        await callback.answer("Ruscha matn topilmadi.", show_alert=True)
        return

    await callback.answer("🎧 Ovoz tayyorlanmoqda...")
    await callback.message.bot.send_chat_action(
        callback.message.chat.id, "record_voice"
    )

    try:
        ru_text = await extract_russian(text)
        if not ru_text:
            await callback.message.answer("⚠️ Ruscha matnni ajratib bo'lmadi.")
            return
        audio = await text_to_speech(ru_text)
    except Exception:
        logger.exception("TTS xatosi")
        await callback.message.answer("⚠️ Ovozga aylantira olmadim.")
        return

    audio_file = BufferedInputFile(audio, filename="reply.mp3")
    await callback.message.answer_audio(
        audio_file,
        title="Talaffuz",
        performer="Rus tili boti",
        caption=ru_text[:1000],
    )
