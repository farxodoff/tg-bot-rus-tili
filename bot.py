"""Bot kirish nuqtasi: polling yoki webhook rejimida ishga tushiradi."""
from __future__ import annotations

import asyncio
import logging
import sys

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiohttp import web

from config import settings
from db import Database
from handlers import build_root_router
from middlewares import DBMiddleware, ThrottlingMiddleware
from scheduler import setup_scheduler


def setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        stream=sys.stdout,
    )
    logging.getLogger("aiogram.event").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


async def set_commands(bot: Bot) -> None:
    await bot.set_my_commands(
        [
            BotCommand(command="start", description="Botni boshlash"),
            BotCommand(command="menu", description="Asosiy menyu"),
            BotCommand(command="stats", description="Statistika"),
            BotCommand(command="leaderboard", description="Top foydalanuvchilar"),
            BotCommand(command="reset", description="Suhbat tarixini tozalash"),
            BotCommand(command="cancel", description="Joriy amalni bekor qilish"),
            BotCommand(command="help", description="Yordam"),
        ]
    )


def build_dispatcher(db: Database) -> Dispatcher:
    dp = Dispatcher(storage=MemoryStorage())

    db_mw = DBMiddleware(db)
    throttle_mw = ThrottlingMiddleware(rate=settings.throttle_rate)

    dp.message.middleware(db_mw)
    dp.callback_query.middleware(db_mw)
    dp.message.middleware(throttle_mw)
    dp.callback_query.middleware(throttle_mw)

    dp.include_router(build_root_router())
    return dp


async def run_polling() -> None:
    setup_logging()
    log = logging.getLogger("bot")

    db = Database(settings.db_path)
    await db.connect()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = build_dispatcher(db)

    scheduler = setup_scheduler(bot, db)
    scheduler.start()

    await set_commands(bot)
    await bot.delete_webhook(drop_pending_updates=False)

    log.info("Bot polling rejimida ishga tushdi")
    try:
        await dp.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await db.close()


async def run_webhook() -> None:
    setup_logging()
    log = logging.getLogger("bot")

    db = Database(settings.db_path)
    await db.connect()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=None),
    )
    dp = build_dispatcher(db)

    scheduler = setup_scheduler(bot, db)
    scheduler.start()

    await set_commands(bot)
    await bot.set_webhook(
        url=settings.webhook_url.rstrip("/") + settings.webhook_path,
        secret_token=settings.webhook_secret or None,
        drop_pending_updates=True,
    )

    app = web.Application()
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.webhook_secret or None,
    ).register(app, path=settings.webhook_path)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, settings.webhook_host, settings.webhook_port)
    await site.start()

    log.info(
        "Bot webhook rejimida ishga tushdi: %s:%s%s",
        settings.webhook_host,
        settings.webhook_port,
        settings.webhook_path,
    )

    try:
        await asyncio.Event().wait()
    finally:
        scheduler.shutdown(wait=False)
        await bot.delete_webhook()
        await bot.session.close()
        await runner.cleanup()
        await db.close()


def main() -> None:
    if settings.use_webhook:
        asyncio.run(run_webhook())
    else:
        asyncio.run(run_polling())


if __name__ == "__main__":
    try:
        main()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot to'xtatildi")
