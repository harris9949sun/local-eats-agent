"""Small SQLite store for user preferences (dietary needs, budget, dislikes...).

Preferences persist between runs, so the agent doesn't have to ask
"any dietary restrictions?" every time.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

ALLOWED_KEYS = {"dietary", "budget", "favorite_cuisines", "dislikes", "neighborhood", "notes"}


class PreferenceStore:
    def __init__(self, db_path: str | Path = "preferences.db", user_id: str = "default"):
        self.user_id = user_id
        self.conn = sqlite3.connect(str(db_path))
        self.conn.execute(
            """CREATE TABLE IF NOT EXISTS preferences (
                   user_id TEXT NOT NULL,
                   key     TEXT NOT NULL,
                   value   TEXT NOT NULL,
                   PRIMARY KEY (user_id, key)
               )"""
        )
        self.conn.commit()

    def get_all(self) -> dict[str, str]:
        rows = self.conn.execute(
            "SELECT key, value FROM preferences WHERE user_id = ?", (self.user_id,)
        ).fetchall()
        return dict(rows)

    def save(self, key: str, value: str) -> None:
        if key not in ALLOWED_KEYS:
            raise ValueError(f"Unknown preference '{key}'. Allowed: {sorted(ALLOWED_KEYS)}")
        self.conn.execute(
            "INSERT INTO preferences (user_id, key, value) VALUES (?, ?, ?) "
            "ON CONFLICT(user_id, key) DO UPDATE SET value = excluded.value",
            (self.user_id, key, value),
        )
        self.conn.commit()

    def clear(self) -> None:
        self.conn.execute("DELETE FROM preferences WHERE user_id = ?", (self.user_id,))
        self.conn.commit()
