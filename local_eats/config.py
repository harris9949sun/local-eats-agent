"""Settings read from environment variables (or a .env file)."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    model: str = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5-5")
    location: str = os.getenv("LOCAL_EATS_LOCATION", "Sacramento, CA")
    provider: str = os.getenv("LOCAL_EATS_PROVIDER", "sample")  # "sample" or "google"
    google_api_key: str | None = os.getenv("GOOGLE_PLACES_API_KEY")
    db_path: str = os.getenv("LOCAL_EATS_DB", "preferences.db")
