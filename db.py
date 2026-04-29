"""SQLite ma'lumotlar bazasi qatlami (aiosqlite)."""
from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from pathlib import Path

import aiosqlite

LEVELS = ("A1", "A2", "B1", "B2")
DEFAULT_LEVEL = "A1"

# Bir mode/foydalanuvchi uchun saqlanadigan eng oxirgi xabarlar soni.
# Eskilari add_message ichida avtomatik o'chiriladi.
MAX_MESSAGES_PER_MODE = 50


SCHEMA = """
CREATE TABLE IF NOT EXISTS users (
    user_id        INTEGER PRIMARY KEY,
    username       TEXT,
    full_name      TEXT,
    level          TEXT NOT NULL DEFAULT 'A1',
    daily_enabled  INTEGER NOT NULL DEFAULT 1,
    points         INTEGER NOT NULL DEFAULT 0,
    streak_days    INTEGER NOT NULL DEFAULT 0,
    last_active    TEXT,
    last_streak    TEXT,
    created_at     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS quiz_results (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    topic       TEXT,
    score       INTEGER NOT NULL,
    total       INTEGER NOT NULL,
    created_at  TEXT NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(user_id)
);

CREATE TABLE IF NOT EXISTS messages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL,
    mode        TEXT NOT NULL,
    role        TEXT NOT NULL,
    content     TEXT NOT NULL,
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS fsm_state (
    key    TEXT PRIMARY KEY,
    state  TEXT,
    data   TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_user_mode
    ON messages(user_id, mode, id DESC);

CREATE INDEX IF NOT EXISTS idx_quiz_user
    ON quiz_results(user_id, created_at DESC);
"""


@dataclass
class User:
    user_id: int
    username: str | None
    full_name: str | None
    level: str
    daily_enabled: bool
    points: int
    streak_days: int
    last_active: str | None
    last_streak: str | None
    created_at: str


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")


class Database:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        # WAL — bir vaqtda o'qish/yozish, kamroq lock.
        await self._conn.execute("PRAGMA journal_mode=WAL")
        await self._conn.execute("PRAGMA synchronous=NORMAL")
        await self._conn.execute("PRAGMA foreign_keys=ON")
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn is not None:
            await self._conn.close()
            self._conn = None

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database connect() chaqirilmagan")
        return self._conn

    # ---- users ----
    async def upsert_user(
        self,
        user_id: int,
        username: str | None,
        full_name: str | None,
    ) -> User:
        now = _now()
        await self.conn.execute(
            """
            INSERT INTO users (user_id, username, full_name, last_active, created_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(user_id) DO UPDATE SET
                username    = excluded.username,
                full_name   = excluded.full_name,
                last_active = excluded.last_active
            """,
            (user_id, username, full_name, now, now),
        )
        await self.conn.commit()
        return await self.get_user(user_id)  # type: ignore[return-value]

    async def get_user(self, user_id: int) -> User | None:
        async with self.conn.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return User(
            user_id=row["user_id"],
            username=row["username"],
            full_name=row["full_name"],
            level=row["level"],
            daily_enabled=bool(row["daily_enabled"]),
            points=row["points"],
            streak_days=row["streak_days"],
            last_active=row["last_active"],
            last_streak=row["last_streak"],
            created_at=row["created_at"],
        )

    async def set_level(self, user_id: int, level: str) -> None:
        if level not in LEVELS:
            raise ValueError(f"Noto'g'ri daraja: {level}")
        await self.conn.execute(
            "UPDATE users SET level = ? WHERE user_id = ?", (level, user_id)
        )
        await self.conn.commit()

    async def set_daily_enabled(self, user_id: int, enabled: bool) -> None:
        await self.conn.execute(
            "UPDATE users SET daily_enabled = ? WHERE user_id = ?",
            (1 if enabled else 0, user_id),
        )
        await self.conn.commit()

    async def add_points(self, user_id: int, delta: int) -> None:
        await self.conn.execute(
            "UPDATE users SET points = points + ? WHERE user_id = ?",
            (delta, user_id),
        )
        await self.conn.commit()

    async def touch_streak(self, user_id: int) -> int:
        """Foydalanuvchi faol bo'lgan kun uchun streak'ni yangilaydi."""
        today = dt.date.today().isoformat()
        user = await self.get_user(user_id)
        if user is None:
            return 0

        if user.last_streak == today:
            return user.streak_days

        new_streak = 1
        if user.last_streak:
            last = dt.date.fromisoformat(user.last_streak)
            if (dt.date.today() - last).days == 1:
                new_streak = user.streak_days + 1

        await self.conn.execute(
            "UPDATE users SET streak_days = ?, last_streak = ? WHERE user_id = ?",
            (new_streak, today, user_id),
        )
        await self.conn.commit()
        return new_streak

    async def daily_subscribers(self) -> list[User]:
        async with self.conn.execute(
            "SELECT * FROM users WHERE daily_enabled = 1"
        ) as cur:
            rows = await cur.fetchall()
        return [
            User(
                user_id=r["user_id"],
                username=r["username"],
                full_name=r["full_name"],
                level=r["level"],
                daily_enabled=bool(r["daily_enabled"]),
                points=r["points"],
                streak_days=r["streak_days"],
                last_active=r["last_active"],
                last_streak=r["last_streak"],
                created_at=r["created_at"],
            )
            for r in rows
        ]

    # ---- quiz ----
    async def save_quiz(
        self, user_id: int, topic: str, score: int, total: int
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO quiz_results (user_id, topic, score, total, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, topic, score, total, _now()),
        )
        await self.conn.commit()

    async def quiz_summary(self, user_id: int) -> dict:
        async with self.conn.execute(
            """
            SELECT COUNT(*) AS games,
                   COALESCE(SUM(score), 0)  AS total_score,
                   COALESCE(SUM(total), 0)  AS total_questions
            FROM quiz_results
            WHERE user_id = ?
            """,
            (user_id,),
        ) as cur:
            row = await cur.fetchone()
        return {
            "games": row["games"],
            "total_score": row["total_score"],
            "total_questions": row["total_questions"],
        }

    async def leaderboard(self, limit: int = 10) -> list[tuple[str, int]]:
        async with self.conn.execute(
            """
            SELECT COALESCE(NULLIF(full_name, ''), username, 'anon') AS name,
                   points
            FROM users
            WHERE points > 0
            ORDER BY points DESC
            LIMIT ?
            """,
            (limit,),
        ) as cur:
            rows = await cur.fetchall()
        return [(r["name"], r["points"]) for r in rows]

    # ---- messages (suhbat tarixi) ----
    async def add_message(
        self, user_id: int, mode: str, role: str, content: str
    ) -> None:
        await self.conn.execute(
            """
            INSERT INTO messages (user_id, mode, role, content, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (user_id, mode, role, content, _now()),
        )
        # Eski xabarlarni trim qilamiz — har mode uchun faqat oxirgi N tasi qoladi.
        await self.conn.execute(
            """
            DELETE FROM messages
            WHERE user_id = ? AND mode = ? AND id NOT IN (
                SELECT id FROM messages
                WHERE user_id = ? AND mode = ?
                ORDER BY id DESC
                LIMIT ?
            )
            """,
            (user_id, mode, user_id, mode, MAX_MESSAGES_PER_MODE),
        )
        await self.conn.commit()

    async def history(
        self, user_id: int, mode: str, limit: int = 12
    ) -> list[dict]:
        async with self.conn.execute(
            """
            SELECT role, content FROM messages
            WHERE user_id = ? AND mode = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (user_id, mode, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [{"role": r["role"], "content": r["content"]} for r in reversed(rows)]

    async def clear_history(self, user_id: int, mode: str | None = None) -> None:
        if mode is None:
            await self.conn.execute(
                "DELETE FROM messages WHERE user_id = ?", (user_id,)
            )
        else:
            await self.conn.execute(
                "DELETE FROM messages WHERE user_id = ? AND mode = ?",
                (user_id, mode),
            )
        await self.conn.commit()
