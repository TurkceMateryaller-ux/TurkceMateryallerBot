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
    openai_api_key: str | None
    openai_model: str
    database_path: str


def load_settings() -> Settings:
    token = (os.getenv("VK_GROUP_TOKEN") or os.getenv("BOT_TOKEN") or "").strip()
    admin_id = os.getenv("ADMIN_VK_ID", "").strip()
    if not token:
        raise RuntimeError("VK_GROUP_TOKEN or BOT_TOKEN is not configured")
    if not admin_id.isdigit():
        raise RuntimeError("ADMIN_VK_ID must be a numeric VK user id")

    return Settings(
        vk_group_token=token,
        vk_group_id=int(os.getenv("VK_GROUP_ID", "240417579")),
        admin_vk_id=int(admin_id),
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5-mini"),
        database_path=os.getenv("DATABASE_PATH", "data/bot.db"),
    )
