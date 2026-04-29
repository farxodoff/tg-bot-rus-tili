"""Barcha routerlarni yig'ib turuvchi paket."""
from aiogram import Router

from . import common, modes, quiz, settings_h, stats, voice


def build_root_router() -> Router:
    root = Router(name="root")
    root.include_router(common.router)
    root.include_router(settings_h.router)
    root.include_router(stats.router)
    root.include_router(quiz.router)
    root.include_router(voice.router)
    root.include_router(modes.router)
    return root
