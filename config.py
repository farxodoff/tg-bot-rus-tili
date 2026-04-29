import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


def _get(key: str, default: str | None = None, *, required: bool = False) -> str:
    value = os.getenv(key, default)
    if required and not value:
        raise RuntimeError(f".env faylida {key} ko'rsatilmagan")
    return value or ""


def _int(key: str, default: int) -> int:
    raw = os.getenv(key)
    return int(raw) if raw else default


def _float(key: str, default: float) -> float:
    raw = os.getenv(key)
    return float(raw) if raw else default


def _ids(key: str) -> set[int]:
    raw = os.getenv(key, "")
    return {int(x) for x in raw.replace(" ", "").split(",") if x}


@dataclass(frozen=True)
class Settings:
    bot_token: str

    gemini_api_key: str
    gemini_model: str
    tts_voice: str

    db_path: Path

    throttle_rate: float
    daily_word_hour: int
    daily_word_minute: int
    timezone: str

    admin_ids: set[int]

    webhook_url: str
    webhook_path: str
    webhook_host: str
    webhook_port: int
    webhook_secret: str

    @property
    def use_webhook(self) -> bool:
        return bool(self.webhook_url)


settings = Settings(
    bot_token=_get("BOT_TOKEN", required=True),
    gemini_api_key=_get("GEMINI_API_KEY", required=True),
    gemini_model=_get("GEMINI_MODEL", "gemini-2.5-flash"),
    tts_voice=_get("TTS_VOICE", "ru-RU-DmitryNeural"),
    db_path=Path(_get("DB_PATH", "data/bot.sqlite3")),
    throttle_rate=_float("THROTTLE_RATE", 1.0),
    daily_word_hour=_int("DAILY_WORD_HOUR", 9),
    daily_word_minute=_int("DAILY_WORD_MINUTE", 0),
    timezone=_get("TIMEZONE", "Asia/Tashkent"),
    admin_ids=_ids("ADMIN_IDS"),
    webhook_url=_get("WEBHOOK_URL", ""),
    webhook_path=_get("WEBHOOK_PATH", "/webhook"),
    webhook_host=_get("WEBHOOK_HOST", "0.0.0.0"),
    webhook_port=_int("WEBHOOK_PORT", 8080),
    webhook_secret=_get("WEBHOOK_SECRET", ""),
)


# Webhook rejimida secret bo'lmasa endpoint himoyasiz qoladi.
if settings.use_webhook and not settings.webhook_secret:
    raise RuntimeError(
        ".env: WEBHOOK_URL berilgan, lekin WEBHOOK_SECRET bo'sh. "
        "Webhook endpoint'ni himoya qilish uchun WEBHOOK_SECRET ni o'rnating."
    )
