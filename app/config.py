"""Runtime settings, loaded from the environment and an optional .env file."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    google_cloud_project: str = "grant-capture-agent"
    google_cloud_location: str = "global"
    embedding_location: str = "us-central1"

    model_agent: str = "gemini-3.8-flash"
    model_grader: str = "gemini-3.5-flash-lite"
    model_drafter: str = "gemini-3.1-pro-preview"
    model_embedding: str = "gemini-embedding-001"
    embedding_dim: int = 768

    database_url: str = "postgresql+psycopg://grant:grant@localhost:5433/grant_capture"
    blob_root: str = "data/blobs"  # local path, or gs://bucket for GCS

    simpler_grants_api_key: SecretStr | None = None
    sam_api_key: SecretStr | None = None
    sam_daily_request_budget: int = 8

    max_attachment_bytes: int = 25 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
