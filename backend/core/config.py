# backend/core/config.py


from pydantic_settings import BaseSettings  # pip install pydantic-settings
from functools import lru_cache


class Settings(BaseSettings):
    # ── Application ─────────────────────────────────────────────────────────────
    app_name: str = "PrepOS API"
    app_version: str = "0.1.0"
    debug: bool = False

    # ── Database ─────────────────────────────────────────────────────────────────
    
    database_url: str = "postgresql+asyncpg://prepos_user:prepos_password@localhost:5432/prepos_db"

    
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"  

    
    cors_origins: list[str] = ["http://localhost:3000", "http://localhost:3001"]

    
    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}



@lru_cache()
def get_settings() -> Settings:
    return Settings()
