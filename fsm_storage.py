"""SQLite asosidagi FSM storage — bot restart bo'lganda state yo'qolmasin."""
from __future__ import annotations

import json
from typing import Any

from aiogram.fsm.state import State
from aiogram.fsm.storage.base import BaseStorage, StorageKey

from db import Database


def _key_to_str(key: StorageKey) -> str:
    return (
        f"{key.bot_id}:{key.chat_id}:{key.user_id}:"
        f"{key.thread_id or 0}:{key.business_connection_id or ''}:{key.destiny}"
    )


class SqliteStorage(BaseStorage):
    """FSM state'ini bot Database'i ichidagi `fsm_state` jadvalida saqlaydi."""

    def __init__(self, db: Database) -> None:
        self._db = db

    async def set_state(self, key: StorageKey, state: State | str | None = None) -> None:
        value: str | None
        if state is None:
            value = None
        elif isinstance(state, State):
            value = state.state
        else:
            value = str(state)

        await self._db.conn.execute(
            """
            INSERT INTO fsm_state (key, state, data) VALUES (?, ?, COALESCE(
                (SELECT data FROM fsm_state WHERE key = ?), '{}'
            ))
            ON CONFLICT(key) DO UPDATE SET state = excluded.state
            """,
            (_key_to_str(key), value, _key_to_str(key)),
        )
        await self._db.conn.commit()

    async def get_state(self, key: StorageKey) -> str | None:
        async with self._db.conn.execute(
            "SELECT state FROM fsm_state WHERE key = ?", (_key_to_str(key),)
        ) as cur:
            row = await cur.fetchone()
        return row["state"] if row else None

    async def set_data(self, key: StorageKey, data: dict[str, Any]) -> None:
        payload = json.dumps(data, ensure_ascii=False)
        await self._db.conn.execute(
            """
            INSERT INTO fsm_state (key, state, data) VALUES (?, NULL, ?)
            ON CONFLICT(key) DO UPDATE SET data = excluded.data
            """,
            (_key_to_str(key), payload),
        )
        await self._db.conn.commit()

    async def get_data(self, key: StorageKey) -> dict[str, Any]:
        async with self._db.conn.execute(
            "SELECT data FROM fsm_state WHERE key = ?", (_key_to_str(key),)
        ) as cur:
            row = await cur.fetchone()
        if not row or not row["data"]:
            return {}
        try:
            return json.loads(row["data"])
        except json.JSONDecodeError:
            return {}

    async def close(self) -> None:
        # Database close() bot.py ichida alohida chaqiriladi.
        return None
