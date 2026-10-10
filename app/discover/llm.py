"""Small structured-output Gemini client shared by the planner, refiner, explainer and eval tools."""

from typing import Protocol, TypeVar

from google.genai import types
from pydantic import BaseModel, ValidationError

from app.config import Settings

T = TypeVar("T", bound=BaseModel)


class JsonError(RuntimeError):
    pass


class JsonModel(Protocol):
    model_id: str
    total_tokens_in: int
    total_tokens_out: int

    def generate(
        self,
        schema: type[T],
        instruction: str,
        content: str,
        cached_content: str | None = None,
    ) -> T: ...


class GeminiJson:
    def __init__(
        self,
        settings: Settings,
        model_id: str | None = None,
        client=None,
        thinking_budget: int | None = None,
    ) -> None:
        from app.analyze.llm import make_client

        self.model_id = model_id or settings.model_agent
        self.thinking_budget = thinking_budget  # None: the model's default thinking
        self.client = client or make_client(settings)
        # every billed call, failed attempts included (budget caps)
        self.total_tokens_in = 0
        self.total_tokens_out = 0

    def generate(
        self,
        schema: type[T],
        instruction: str,
        content: str,
        cached_content: str | None = None,
    ) -> T:
        config = types.GenerateContentConfig(
            # with a context cache the instruction lives in the cache
            system_instruction=None if cached_content else instruction,
            temperature=0,
            response_mime_type="application/json",
            response_schema=schema,
            cached_content=cached_content,
            thinking_config=types.ThinkingConfig(thinking_budget=self.thinking_budget)
            if self.thinking_budget is not None
            else None,
        )
        error = ""
        for attempt in range(2):  # one retry with the validation error appended
            text = (
                content
                if attempt == 0
                else f"{content}\n\nYour previous answer failed validation: {error}. "
                "Return JSON that matches the schema."
            )
            response = self.client.models.generate_content(
                model=self.model_id, contents=text, config=config
            )
            usage = response.usage_metadata
            if usage:  # thinking tokens are billed as output
                self.total_tokens_in += usage.prompt_token_count or 0
                self.total_tokens_out += (usage.candidates_token_count or 0) + (
                    getattr(usage, "thoughts_token_count", 0) or 0
                )
            try:
                return schema.model_validate_json(response.text or "")
            except ValidationError as exc:
                error = str(exc)[:500]
        raise JsonError(error)
