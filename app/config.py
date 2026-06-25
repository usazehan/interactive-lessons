"""Application configuration.

Centralizes settings via pydantic-settings so they're typed, validated, and
easy to override through environment variables (or a local .env file), e.g.
switching the database path or toggling debug.

Field names map to env vars case-insensitively: ``app_name`` <- ``APP_NAME``,
``database_path`` <- ``DATABASE_PATH``, etc.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "interactive-lessons"
    debug: bool = False
    # SQLite database path. ":memory:" gives an ephemeral DB (used by tests).
    database_path: str = "interactive_lessons.db"
    # Reading-session snapshots are ephemeral; prune ones idle longer than this.
    session_ttl_seconds: int = 7 * 24 * 3600  # 7 days


settings = Settings()
