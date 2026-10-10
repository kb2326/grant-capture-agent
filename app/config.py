"""Runtime settings, loaded from the environment and an optional .env file."""

import os
from functools import lru_cache
from typing import Literal

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
    # ---- M2 Discover ----
    model_embedding_local: str = (
        "google/embeddinggemma-2"  # Apache-2.0, not gated; 768-d, 8K context
    )
    local_query_prompt: str = "SearchQuery"
    local_document_prompt: str = "Document"
    embedding_batch_size: int = (
        50  # live check 2026-10-09: gemini-embedding-001 accepts batched inputs
    )
    price_embedding_per_m: float = 0.15  # gemini-embedding-001, per 1M input tokens
    price_grader_input_per_m: float = 0.25  # gemini-3.5-flash-lite (conservative; real spend checked in Cloud Monitoring)
    price_grader_output_per_m: float = 1.50
    rerank_model: str = "semantic-ranker-default-004"
    price_rank_per_1k: float = 1.0  # Vertex AI Ranking API, per 1,000 queries
    discover_embedding: Literal["gemini", "local"] = "gemini"  # M2 ablation, ADR-0020
    discover_rerank: bool = (
        False  # M2 ablation: no gain (nDCG@10 0.512 vs 0.514), extra latency
    )
    discover_tau: float | None = None  # V3 threshold, tuned on dev queries
    discover_k: int = 5
    discover_max_iterations: int = 3
    discover_v4_transport: Literal["direct", "a2a"] = "direct"
    discover_v4_max_checks: int = 5
    analyze_a2a_url: str = "http://127.0.0.1:8001"
    discover_eval_budget_usd: float = 1.0  # hard cap per Discover eval stage
    # ---- M3 Draft ----
    draft_eval_budget_usd: float = 1.0  # hard cap per Draft eval stage
    draft_cache_ttl_s: int = 1800
    draft_top_k: int = 8
    draft_min_relevant: int = 2
    draft_max_rewrites: int = 2
    draft_variant: Literal["B0", "B1"] = "B0"  # set by the M3 ablation (ADR-0018)
    draft_thinking_budget: int = 1024  # thinking tokens are billed as output; M3 runs showed up to 13k per section
    # ---- M4 local UI ----
    ui_session_budget_usd: float = (
        0.50  # live UI actions stop once this is spent in one API process
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
