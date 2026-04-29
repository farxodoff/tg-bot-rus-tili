"""Kunlik so'z (Word of the Day) joylashtiruvchi."""
from __future__ import annotations

import asyncio
import logging

from aiogram import Bot
from aiogram.exceptions import TelegramForbiddenError, TelegramNotFound
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from ai_client import chat_json
from config import settings
from db import Database
from prompts import DAILY_WORD_SYSTEM

logger = logging.getLogger(__name__)


def format_daily_word(data: dict) -> str:
    return (
        "🌅 *Kunning so'zi*\n\n"
        f"🇷🇺 *{data.get('word_ru', '?')}*\n"
        f"🔊 _{data.get('translit', '')}_\n"
        f"🇺🇿 {data.get('word_uz', '')}\n\n"
        f"📝 {data.get('example_ru', '')}\n"
        f"➡️ {data.get('example_uz', '')}"
    )


async def send_daily_word(bot: Bot, db: Database) -> None:
    try:
        data = await chat_json(
            DAILY_WORD_SYSTEM,
            "Bugungi yangi so'zni tanlang.",
        )
    except Exception:
        logger.exception("Kunlik so'zni generatsiya qilib bo'lmadi")
        return

    text = format_daily_word(data)
    subscribers = await db.daily_subscribers()
    logger.info("Kunlik so'z %d obunachiga yuborilmoqda", len(subscribers))

    for user in subscribers:
        try:
            await bot.send_message(user.user_id, text, parse_mode="Markdown")
        except (TelegramForbiddenError, TelegramNotFound):
            await db.set_daily_enabled(user.user_id, False)
        except Exception:
            logger.exception("user_id=%s ga yuborib bo'lmadi", user.user_id)
        await asyncio.sleep(0.05)


def setup_scheduler(bot: Bot, db: Database) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler(timezone=settings.timezone)
    scheduler.add_job(
        send_daily_word,
        CronTrigger(
            hour=settings.daily_word_hour,
            minute=settings.daily_word_minute,
        ),
        kwargs={"bot": bot, "db": db},
        id="daily_word",
        replace_existing=True,
    )
    return scheduler
