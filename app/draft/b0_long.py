"""B0: the whole labeled company corpus in a Gemini context cache; one call per section (M3 spec §3.4)."""

import logging

from google.genai import types

from app.contracts import DraftTask
from app.draft.corpus import LabeledChunk, render_chunks
from app.draft.generate import DRAFT_RULES, generate_section

log = logging.getLogger(__name__)


class CorpusCache:
    def __init__(
        self, client, model_id: str, chunks: list[LabeledChunk], ttl_s: int
    ) -> None:
        self.client, self.model_id, self.chunks, self.ttl_s = (
            client,
            model_id,
            chunks,
            ttl_s,
        )
        self._name: str | None = None
        self._tried = False

    def name(self) -> str | None:
        if not self._tried:
            self._tried = True
            try:  # caching has a minimum size and can fail; drafting must still work without it
                cache = self.client.caches.create(
                    model=self.model_id,
                    config=types.CreateCachedContentConfig(
                        contents=[
                            types.Content(
                                role="user",
                                parts=[
                                    types.Part.from_text(
                                        text=render_chunks(self.chunks)
                                    )
                                ],
                            )
                        ],
                        system_instruction=DRAFT_RULES,
                        ttl=f"{self.ttl_s}s",
                    ),
                )
                self._name = cache.name
            except Exception as exc:
                log.warning("context cache unavailable, drafting uncached: %s", exc)
        return self._name

    def delete(self) -> None:
        if self._name:
            try:
                self.client.caches.delete(name=self._name)
            except Exception:
                pass


def draft_b0(
    llm, task: DraftTask, chunks: list[LabeledChunk], cache: CorpusCache | None
):
    name = cache.name() if cache else None
    if name:
        try:
            return generate_section(llm, task, chunks, cached_content=name)
        except Exception as exc:  # expired or evicted cache: run the same call uncached
            log.warning("cached call failed, retrying uncached: %s", exc)
    return generate_section(llm, task, chunks)
