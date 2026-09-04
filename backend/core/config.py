from functools import lru_cache
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Dynamically locate the .env file relative to this config file
# config.py is in backend/core/ -> parent is backend/ -> parent.parent is project root
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    # ── Application ─────────────────────────────────────────────────────────────
    app_name: str = "PrepOS API"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── Database ─────────────────────────────────────────────────────────────────
    database_url: str = "postgresql+asyncpg://prepos_user:prepos_password@localhost:5432/prepos_db"

    # ── AI / LLM ────────────────────────────────────────────────────────────────
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"

    # ── CORS ────────────────────────────────────────────────────────────────────
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # Check both backend/.env and root .env automatically
    model_config = SettingsConfigDict(
        env_file=(BASE_DIR / ".env", BASE_DIR.parent / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )


@lru_cache()
def get_settings() -> Settings:
    return Settings()