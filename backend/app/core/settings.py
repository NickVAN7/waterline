"""Application settings from environment variables (and the repo-root `.env` in local dev)."""

from functools import lru_cache
from pathlib import Path

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict
from sqlalchemy import URL

# backend/app/core/settings.py -> repo root. Missing in containers, which get real env vars.
REPO_ROOT_ENV_FILE = Path(__file__).resolve().parents[3] / ".env"

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
