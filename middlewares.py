"""Custom middlewares: DI va throttling."""
from __future__ import annotations

import logging
import time
from typing import Any, Awaitable, Callable

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from db import Database, User

logger = logging.getLogger(__name__)

# Foydalanuvchi ma'lumotlari shu muddat ichida qayta DB'dan o'qilmaydi.
_USER_CACHE_TTL = 30.0


class DBMiddleware(BaseMiddleware):
    """Har bir handler'ga `db` obyekti uzatadi va foydalanuvchini upsert qiladi."""

    def __init__(self, db: Database) -> None:
        self.db = db
        # user_id -> (User, fetched_at). Upsert spam'ni kamaytiradi.
        self._cache: dict[int, tuple[User, float]] = {}

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        data["db"] = self.db

        from_user = getattr(event, "from_user", None)
        if from_user is not None:
            now = time.monotonic()
            cached = self._cache.get(from_user.id)
            if cached and now - cached[1] < _USER_CACHE_TTL:
                user = cached[0]
            else:
                user = await self.db.upsert_user(
                    user_id=from_user.id,
                    username=from_user.username,
                    full_name=from_user.full_name,
                )
                self._cache[from_user.id] = (user, now)
                # Vaqti-vaqti bilan eski yozuvlarni tozalab turamiz.
                if len(self._cache) > 1000:
                    cutoff = now - _USER_CACHE_TTL
                    self._cache = {
                        uid: v for uid, v in self._cache.items() if v[1] > cutoff
                    }
            data["user"] = user

        return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
    """Bir foydalanuvchidan ketma-ket xabarlarni cheklaydi."""

    # Ko'p foydalanuvchi to'planib qolsa periodik tozalash
    _CLEANUP_THRESHOLD = 1000

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

        # Eski yozuvlarni tozalash (rate'dan uzoq oldin kirgan foydalanuvchilar).
        if len(self._last) > self._CLEANUP_THRESHOLD:
            cutoff = now - max(self.rate * 10, 60.0)
            self._last = {uid: t for uid, t in self._last.items() if t > cutoff}

        return await handler(event, data)
