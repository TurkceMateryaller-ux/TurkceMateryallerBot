from __future__ import annotations

import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    telegram_bot_token: str
    admin_telegram_id: int | None
    gemini_api_key: str | None
    gemini_model: str
    database_path: str


def load_settings() -> Settings:
    token = (os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN or TELEGRAM_BOT_TOKEN is not configured")
    admin = os.getenv("ADMIN_TELEGRAM_ID", "").strip()
    if admin and not admin.isdigit():
        raise RuntimeError("ADMIN_TELEGRAM_ID must be numeric")
    return Settings(
        telegram_bot_token=token,
        admin_telegram_id=int(admin) if admin else None,
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-3.5-flash-lite"),
        database_path=os.getenv("DATABASE_PATH", "data/bot.db"),
    )
