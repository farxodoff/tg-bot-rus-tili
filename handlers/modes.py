"""6 ta o'rganish rejimi: chat handler + TTS tugmasi."""
from __future__ import annotations

import logging

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import BufferedInputFile, CallbackQuery, Message

from google.genai import errors

from ai_client import chat, has_russian, text_to_speech_mixed
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
    text = f"{MODE_TITLES[mode]}\n\n{intro}"
    try:
        await callback.message.edit_text(text, reply_markup=back_menu())
    except Exception:
        await callback.message.answer(text, reply_markup=back_menu())

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
    except errors.APIError as e:
        code = getattr(e, "code", None)
        logger.warning("Gemini API xatosi: code=%s", code)
        if code == 503:
            await message.answer(
                "⏳ Gemini server hozir juda band. 30 soniyadan keyin qayta yuboring."
            )
        elif code == 429:
            await message.answer(
                "⏳ Bepul tarif limiti tugadi (daqiqada 15 ta so'rov). "
                "Bir daqiqa kutib qayta yuboring."
            )
        else:
            await message.answer(
                f"⚠️ Gemini xatosi (kod: {code}). Biroz keyinroq qayta urinib ko'ring."
            )
        return
    except Exception:
        logger.exception("AI chat kutilmagan xatosi")
        await message.answer(
            "⚠️ Hozir javob bera olmadim. Biroz keyinroq qayta urinib ko'ring."
        )
        return

    await db.add_message(user_id, mode, "user", message.text)
    # AI matnida `<`, `>`, `&` bo'lishi mumkin — HTML parse rejimida xato bermasin.
    await message.answer(reply, parse_mode=None, reply_markup=reply_actions())
    await db.add_message(user_id, mode, "assistant", reply)

    await db.add_points(user_id, 1)
    await db.touch_streak(user_id)


@router.callback_query(F.data == "tts")
async def on_tts(callback: CallbackQuery) -> None:
    """Bot javobini har til o'z ovozi bilan o'qib yuboradi."""
    if not callback.message:
        return
    text = callback.message.text or callback.message.caption or ""

    if not text or not has_russian(text):
        await callback.answer("Ruscha matn topilmadi.", show_alert=True)
        return

    await callback.answer("🎧 Ovoz tayyorlanmoqda...")
    await callback.message.bot.send_chat_action(
        callback.message.chat.id, "record_voice"
    )

    try:
        audio, caption = await text_to_speech_mixed(text)
        if not audio:
            await callback.message.answer("⚠️ O'qish uchun matn topilmadi.")
            return
    except Exception:
        logger.exception("TTS xatosi")
        await callback.message.answer("⚠️ Ovozga aylantira olmadim.")
        return

    audio_file = BufferedInputFile(audio, filename="reply.mp3")
    await callback.message.answer_audio(
        audio_file,
        title="Talaffuz",
        performer="Rus tili boti",
        caption=caption[:1000],
    )
