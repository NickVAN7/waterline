"""Application settings from environment variables (and the repo-root `.env` in local dev)."""

from datetime import timedelta
from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

# backend/app/core/settings.py -> repo root. Missing in containers, which get real env vars.
REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

# `last_seen_at` is written at most this often (design-doc §4, "Sessions").
LAST_SEEN_INTERVAL = timedelta(minutes=5)

# Created by docker/postgres/initdb/ next to the dev database; tests never touch dev data.
TEST_DATABASE_NAME = "waterline_test"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=REPO_ROOT_ENV_FILE, extra="ignore")

    postgres_user: str
    postgres_password: SecretStr
    postgres_db: str
    postgres_host: str = "localhost"
    postgres_port: int = 5432

    # Swagger UI and the OpenAPI schema under /api. Off unless enabled (on in dev and test via
    # .env; off in production) — build-plan.md, "API foundations".
    api_docs_enabled: bool = False

    # Session lengths (design-doc §4, "Sessions"): a session ends after this long without a
    # request, and in any case this long after sign-in. In env, ISO 8601 durations (`P7D`).
    # The idle timeout must exceed the gap between `last_seen_at` writes, or an active user's
    # session would lapse between them.
    session_idle_timeout: timedelta = Field(timedelta(days=7), gt=LAST_SEEN_INTERVAL)
    session_lifetime: timedelta = Field(timedelta(days=30), gt=timedelta(0))

    def database_url(self, *, database: str | None = None) -> URL:
        return URL.create(
            "postgresql+psycopg",
            username=self.postgres_user,
            password=self.postgres_password.get_secret_value(),
            host=self.postgres_host,
            port=self.postgres_port,
            database=database or self.postgres_db,
        )

    def test_database_url(self) -> URL:
        return self.database_url(database=TEST_DATABASE_NAME)


@lru_cache
def get_settings() -> Settings:
    return Settings()  # pyright: ignore[reportCallIssue] -- fields come from the environment
