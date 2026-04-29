"""Ovozli xabarlarni qabul qilish: Gemini multimodal bilan transkripsiya, keyin chat'ga uzatish."""
from __future__ import annotations

import html
import logging
from io import BytesIO

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from google.genai import errors

from ai_client import chat, speech_to_text
from db import Database, User
from keyboards import back_menu, reply_actions
from prompts import mode_prompt
from states import KEY_MODE, ModeState

router = Router(name="voice")
logger = logging.getLogger(__name__)

MAX_VOICE_BYTES = 20 * 1024 * 1024  # 20 MB


@router.message(F.voice | F.audio)
async def on_voice(
    message: Message, state: FSMContext, db: Database, user: User
) -> None:
    file = message.voice or message.audio
    if file.file_size and file.file_size > MAX_VOICE_BYTES:
        await message.answer("⚠️ Audio juda katta (20 MB dan oshmasligi kerak).")
        return

    await message.bot.send_chat_action(message.chat.id, "typing")

    buffer = BytesIO()
    try:
        await message.bot.download(file, destination=buffer)
        audio_bytes = buffer.getvalue()
    except Exception:
        logger.exception("Audio yuklab olishda xato")
        await message.answer("⚠️ Audio yuklab olinmadi.")
        return

    mime = "audio/ogg" if message.voice else (file.mime_type or "audio/mpeg")

    try:
        transcript = await speech_to_text(audio_bytes, mime=mime)
    except errors.APIError as e:
        code = getattr(e, "code", None)
        logger.warning("STT API xatosi: code=%s", code)
        if code == 503:
            await message.answer("⏳ Gemini server band. 30 soniyadan keyin qayta urinib ko'ring.")
        else:
            await message.answer(f"⚠️ Ovozni tanib bo'lmadi (kod: {code}).")
        return
    except Exception:
        logger.exception("STT kutilmagan xatosi")
        await message.answer("⚠️ Ovozni matnga aylantirib bo'lmadi.")
        return

    if not transcript:
        await message.answer("⚠️ Ovozli xabar bo'sh ko'rindi.")
        return

    await message.answer(
        f"📝 <b>Sizning ovozingiz:</b>\n<i>{html.escape(transcript)}</i>"
    )

    current_state = await state.get_state()
    if current_state != ModeState.chatting.state:
        await message.answer(
            "Avval menyudan rejim tanlang — keyin ovoz orqali ham mashq qila olasiz.",
            reply_markup=back_menu(),
        )
        return

    data = await state.get_data()
    mode = data.get(KEY_MODE)
    if not mode:
        await message.answer("Avval rejim tanlang.", reply_markup=back_menu())
        return

    history = await db.history(message.from_user.id, mode, limit=12)
    system = mode_prompt(mode, user.level)

    try:
        reply = await chat(system, history, transcript)
    except Exception:
        logger.exception("Chat xatosi (voice)")
        await message.answer("⚠️ Javob bera olmadim.")
        return

    await db.add_message(message.from_user.id, mode, "user", transcript)
    await message.answer(reply, parse_mode=None, reply_markup=reply_actions())
    await db.add_message(message.from_user.id, mode, "assistant", reply)

    await db.add_points(message.from_user.id, 2)
    await db.touch_streak(message.from_user.id)
