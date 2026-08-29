from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


load_dotenv()


@dataclass(frozen=True)
class Settings:
    vk_group_token: str
    vk_group_id: int
    admin_vk_id: int
    gemini_api_key: str | None
    gemini_model: str
    database_path: str


def load_settings() -> Settings:
    # BotHost always injects its required token field as BOT_TOKEN. Prefer it
    # over a possibly stale VK_GROUP_TOKEN left from an earlier deployment.
    token = (os.getenv("BOT_TOKEN") or os.getenv("VK_GROUP_TOKEN") or "").strip()
    admin_id = os.getenv("ADMIN_VK_ID", "").strip()
    if not token:
        raise RuntimeError("VK_GROUP_TOKEN or BOT_TOKEN is not configured")
    if not admin_id.isdigit():
        raise RuntimeError("ADMIN_VK_ID must be a numeric VK user id")

    return Settings(
        vk_group_token=token,
        vk_group_id=int(os.getenv("VK_GROUP_ID", "240417579")),
        admin_vk_id=int(admin_id),
        gemini_api_key=os.getenv("GEMINI_API_KEY") or None,
        gemini_model=os.getenv("GEMINI_MODEL", "gemini-2.5-flash"),
        database_path=os.getenv("DATABASE_PATH", "data/bot.db"),
    )
