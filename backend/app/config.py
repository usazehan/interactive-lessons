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
    # Auth (JWT). OVERRIDE jwt_secret_key in production via JWT_SECRET_KEY.
    jwt_secret_key: str = "dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 15
    refresh_token_expire_days: int = 7
    reset_token_expire_minutes: int = 60
    # Used to build links in verification / reset emails.
    app_base_url: str = "http://localhost:8000"
    # Browser origins allowed to call the API (the frontend). Override via
    # CORS_ORIGINS as a JSON array, e.g. '["https://app.example.com"]'.
    cors_origins: list[str] = ["http://localhost:3000"]


settings = Settings()
