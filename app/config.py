"""Runtime settings, loaded from the environment and an optional .env file."""

import os
from functools import lru_cache

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def load_secret(secret_id: str, project: str, client=None) -> str | None:
    """Read the latest version of a Secret Manager secret; None if missing or unreadable."""
    if client is None:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
    try:
        response = client.access_secret_version(
            name=f"projects/{project}/secrets/{secret_id}/versions/latest"
        )
    except Exception:
        return None
    return response.payload.data.decode("utf-8")


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
    model_labeler: str = (
        "gemini-3.1-pro-preview"  # AI (silver) labels; must differ from model_agent
    )
    model_embedding: str = "gemini-embedding-001"
    embedding_dim: int = 768

    database_url: str = "postgresql+psycopg://grant:grant@localhost:5433/grant_capture"
    blob_root: str = "data/blobs"  # local path, or gs://bucket for GCS

    simpler_grants_api_key: SecretStr | None = None
    sam_api_key: SecretStr | None = None
    sam_daily_request_budget: int = 8

    max_attachment_bytes: int = 25 * 1024 * 1024
    analyze_context_budget: int = 300_000
    analyze_window_pages: int = 5
    price_agent_input_per_m: float = (
        0.75  # gemini-3.8-flash, launch pricing through 2026-12-31
    )
    price_agent_output_per_m: float = 3.75
    price_labeler_input_per_m: float = 2.0  # gemini-3.1-pro-preview
    price_labeler_output_per_m: float = 12.0
    eval_budget_usd: float = (
        1.25  # hard cap per eval variant run (estimated Gemini spend)
    )

    @model_validator(mode="after")
    def _secrets_from_secret_manager(self) -> "Settings":
        password = os.environ.get("DB_PASSWORD")
        if password and "$(DB_PASSWORD)" in self.database_url:
            object.__setattr__(
                self,
                "database_url",
                self.database_url.replace("$(DB_PASSWORD)", password),
            )
        if os.environ.get("USE_SECRET_MANAGER") != "1":
            return self
        for field, secret_id in (
            ("simpler_grants_api_key", "simpler-grants-api-key"),
            ("sam_api_key", "sam-api-key"),
        ):
            if getattr(self, field) is None:
                value = load_secret(secret_id, self.google_cloud_project)
                if value:
                    object.__setattr__(self, field, SecretStr(value))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
