"""Gemini structured-output client for brief extraction."""

import time
from dataclasses import dataclass
from typing import Protocol

from google import genai
from google.genai import types
from pydantic import ValidationError

from app.config import Settings
from app.contracts import ModelBrief


class ExtractionError(RuntimeError):
    pass


@dataclass
class LlmResult:
    brief: ModelBrief
    tokens_in: int
    tokens_out: int
    latency_s: float


class BriefModel(Protocol):
    model_id: str

    def extract(self, parts: list, instruction: str) -> LlmResult: ...


def make_client(settings: Settings) -> genai.Client:
    """Vertex AI client that waits and retries on rate limits (429) and transient server errors."""
    return genai.Client(
        vertexai=True,
        project=settings.google_cloud_project,
        location=settings.google_cloud_location,
        http_options=types.HttpOptions(
            retry_options=types.HttpRetryOptions(
                attempts=6,
                initial_delay=5,
                max_delay=90,
                http_status_codes=[408, 429, 500, 502, 503, 504],
            )
        ),
    )


class GeminiBriefModel:
    def __init__(self, settings: Settings, client: genai.Client | None = None) -> None:
        self.model_id = settings.model_agent
        self.client = client or make_client(settings)

    def extract(self, parts: list, instruction: str) -> LlmResult:
        config = types.GenerateContentConfig(
            system_instruction=instruction,
            temperature=0,
            response_mime_type="application/json",
            response_schema=ModelBrief,
        )
        start, tokens_in, tokens_out, error = time.monotonic(), 0, 0, ""
        for attempt in range(
            2
        ):  # one retry with the validation error appended (spec §8)
            contents = (
                parts
                if attempt == 0
                else [
                    *parts,
                    types.Part.from_text(
                        text=f"Your previous answer failed validation: {error}. Return JSON that matches the schema."
                    ),
                ]
            )
            response = self.client.models.generate_content(
                model=self.model_id, contents=contents, config=config
            )
            usage = response.usage_metadata
            tokens_in += (usage.prompt_token_count or 0) if usage else 0
            tokens_out += (usage.candidates_token_count or 0) if usage else 0
            try:
                brief = ModelBrief.model_validate_json(response.text or "")
            except ValidationError as exc:
                error = str(exc)[:500]
                continue
            return LlmResult(brief, tokens_in, tokens_out, time.monotonic() - start)
        raise ExtractionError(error)
