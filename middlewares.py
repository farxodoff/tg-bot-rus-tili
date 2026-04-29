"""Custom middlewares: DI va throttling."""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from db import Database

logger = logging.getLogger(__name__)


class DBMiddleware(BaseMiddleware):
    """Har bir handler'ga `db` obyekti uzatadi va foydalanuvchini upsert qiladi."""

    def __init__(self, db: Database) -> None:
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["db"] = self.db

        from_user = getattr(event, "from_user", None)
        if from_user is not None:
            user = await self.db.upsert_user(
                user_id=from_user.id,
                username=from_user.username,
                full_name=from_user.full_name,
            )
            data["user"] = user

        return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
    """Bir foydalanuvchidan ketma-ket xabarlarni cheklaydi."""

    def __init__(self, rate: float = 1.0) -> None:
        self.rate = rate
        self._last: dict[int, float] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        from_user = getattr(event, "from_user", None)
        if from_user is None:
            return await handler(event, data)

        now = time.monotonic()
        last = self._last.get(from_user.id, 0.0)

        if now - last < self.rate:
            if isinstance(event, Message):
                await event.answer("⏳ Birozdan keyin qayta urinib ko'ring.")
            elif isinstance(event, CallbackQuery):
                await event.answer("⏳ Sekinroq", show_alert=False)
            return None

        self._last[from_user.id] = now
        return await handler(event, data)
