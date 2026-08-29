from __future__ import annotations

import sqlite3
from pathlib import Path


class Database:
    def __init__(self, path: str):
        db_path = Path(path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = sqlite3.connect(db_path, check_same_thread=False)
        self.connection.row_factory = sqlite3.Row

    def initialize(self) -> None:
        self.connection.executescript(
            """
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users (
                vk_id INTEGER PRIMARY KEY,
                subscribed INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS requests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                vk_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS materials (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                description TEXT NOT NULL DEFAULT '',
                level TEXT NOT NULL DEFAULT 'A1',
                topic TEXT NOT NULL DEFAULT '',
                preview_attachment TEXT,
                file_attachment TEXT,
                published INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        self.connection.commit()

    def ensure_user(self, vk_id: int) -> None:
        self.connection.execute(
            "INSERT OR IGNORE INTO users(vk_id) VALUES (?)", (vk_id,)
        )
        self.connection.commit()

    def set_subscription(self, vk_id: int, subscribed: bool) -> None:
        self.ensure_user(vk_id)
        self.connection.execute(
            "UPDATE users SET subscribed=?, updated_at=CURRENT_TIMESTAMP WHERE vk_id=?",
            (int(subscribed), vk_id),
        )
        self.connection.commit()

    def add_request(self, vk_id: int, text: str) -> int:
        cursor = self.connection.execute(
            "INSERT INTO requests(vk_id, text) VALUES (?, ?)", (vk_id, text.strip())
        )
        self.connection.commit()
        return int(cursor.lastrowid)

    def list_user_requests(self, vk_id: int) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT id, text, status, created_at FROM requests WHERE vk_id=? "
                "ORDER BY id DESC LIMIT 10",
                (vk_id,),
            )
        )

    def list_materials(self) -> list[sqlite3.Row]:
        return list(
            self.connection.execute(
                "SELECT * FROM materials WHERE published=1 ORDER BY id DESC LIMIT 20"
            )
        )

