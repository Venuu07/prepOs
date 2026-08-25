# backend/core/config.py
#
# CONCEPT: Configuration Management
#
# Every application needs configuration: database URLs, API keys, feature flags.
# The wrong way: hardcode values in your code → secrets leak into Git, 
#                values are hard to change between environments (dev/prod).
# The right way: environment variables + a typed config class that reads them.
#
# Pydantic's BaseSettings does two things automatically:
#   1. Reads values from environment variables (and .env files)
#   2. Validates and coerces types (e.g., "5432" string → int 5432)
#
# If a required variable is missing, the app crashes at startup with a clear
# error message — not silently deep in the middle of a request.

from pydantic_settings import BaseSettings  # pip install pydantic-settings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Application ─────────────────────────────────────────────────────────────
    app_name: str = "PrepOS API"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── Database ─────────────────────────────────────────────────────────────────
    # DATABASE_URL format: postgresql+asyncpg://user:password@host:port/dbname
    # asyncpg is the async PostgreSQL driver — FastAPI is async-first.
    database_url: str = "postgresql+asyncpg://prepos_user:prepos_password@localhost:5432/prepos_db"

    # ── AI Provider ──────────────────────────────────────────────────────────────
    # We'll use Gemini. Get your key at: https://aistudio.google.com/
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"  # fast + cheap for development

    # ── CORS ─────────────────────────────────────────────────────────────────────
    # CONCEPT: CORS (Cross-Origin Resource Sharing)
    # Browsers block JavaScript from fetching data from a different domain by default.
    # Our Next.js app runs on localhost:3000, backend on localhost:8000.
    # That's two different "origins." Without CORS config, the browser blocks it.
    # We tell FastAPI: "Allow requests from localhost:3000."
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    # ── Pydantic model config ─────────────────────────────────────────────────────
    # This tells BaseSettings where to find the .env file.
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


# CONCEPT: lru_cache (Least Recently Used Cache)
# Settings reads from the .env file every time it's instantiated.
# @lru_cache means: call this function once, cache the result, return the 
# cached result on all future calls. So we only read .env once at startup.
# 
# Usage throughout the app: from backend.core.config import get_settings
#                           settings = get_settings()
@lru_cache()
def get_settings() -> Settings:
    return Settings()
