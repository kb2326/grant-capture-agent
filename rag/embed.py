"""Embedders for cards and queries: Gemini (cloud) and EmbeddingGemma 2 (local CPU). M2 spec §3.2."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Protocol

from google.genai import types
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from db.models import OpportunityCardRow

if TYPE_CHECKING:  # rag/ never imports the app at runtime (no ADK, no import cycle)
    from app.config import Settings

log = logging.getLogger(__name__)
COLUMNS = {"gemini": "emb_gemini", "local": "emb_local"}


class Embedder(Protocol):
    name: str
    tokens: int  # billed input tokens so far (0 for local)

    def embed_documents(self, texts: list[str]) -> list[list[float]]: ...

    def embed_query(self, text: str) -> list[float]: ...


class GeminiEmbedder:
    name = "gemini"

    def __init__(
        self, settings: Settings, client=None, batch_size: int | None = None
    ) -> None:
        if client is None:
            from app.analyze.llm import make_client

            client = make_client(
                settings.model_copy(
                    update={"google_cloud_location": settings.embedding_location}
                )
            )
        self.client, self.model = client, settings.model_embedding
        self.dim = settings.embedding_dim
        self.batch = batch_size or settings.embedding_batch_size
        self.tokens = 0

    def _embed(self, texts: list[str], task: str) -> list[list[float]]:
        out: list[list[float]] = []
        for i in range(0, len(texts), self.batch):
            chunk = texts[i : i + self.batch]
            resp = self.client.models.embed_content(
                model=self.model,
                contents=chunk,
                config=types.EmbedContentConfig(
                    task_type=task, output_dimensionality=self.dim
                ),
            )
            for text, emb in zip(chunk, resp.embeddings, strict=True):
                stats = getattr(emb, "statistics", None)
                self.tokens += int(getattr(stats, "token_count", 0) or len(text) // 4)
                out.append(list(emb.values))
        return out

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return self._embed(texts, "RETRIEVAL_DOCUMENT")

    def embed_query(self, text: str) -> list[float]:
        return self._embed([text], "RETRIEVAL_QUERY")[0]


class LocalEmbedder:
    name = "local"

    def __init__(self, settings: Settings, model=None) -> None:
        if model is None:
            # optional group: uv sync --group local-embed
            from sentence_transformers import SentenceTransformer

            model = SentenceTransformer(settings.model_embedding_local, device="cpu")
        self.model, self.tokens = model, 0
        self.doc_prompt = settings.local_document_prompt
        self.query_prompt = settings.local_query_prompt

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        vecs = self.model.encode(
            texts, prompt_name=self.doc_prompt, batch_size=8, normalize_embeddings=True
        )
        return [[float(x) for x in v] for v in vecs]

    def embed_query(self, text: str) -> list[float]:
        vec = self.model.encode(
            [text], prompt_name=self.query_prompt, normalize_embeddings=True
        )[0]
        return [float(x) for x in vec]


def make_embedder(name: str, settings: Settings) -> Embedder:
    return GeminiEmbedder(settings) if name == "gemini" else LocalEmbedder(settings)


def embed_cards(
    session: Session,
    embedder: Embedder,
    *,
    column: str,
    price_per_m: float,
    max_usd: float | None = None,
    batch: int = 50,
) -> dict:
    """Embed every card whose `column` is empty. Failed batches stay empty and are counted; a budget stops the run."""
    if column not in COLUMNS.values():
        raise ValueError(f"unknown embedding column {column!r}")
    col = getattr(OpportunityCardRow, column)
    ids = list(
        session.scalars(select(OpportunityCardRow.opportunity_id).where(col.is_(None)))
    )
    start = embedder.tokens
    stats: dict = {"embedded": 0, "failed": 0, "cost_usd": 0.0, "stopped": None}
    for i in range(0, len(ids), batch):
        if max_usd is not None and stats["cost_usd"] >= max_usd:
            stats["stopped"] = "budget"
            break
        chunk = ids[i : i + batch]
        rows = {
            r.opportunity_id: r.text
            for r in session.execute(
                select(
                    OpportunityCardRow.opportunity_id, OpportunityCardRow.text
                ).where(OpportunityCardRow.opportunity_id.in_(chunk))
            )
        }
        try:
            vecs = embedder.embed_documents([rows[c] for c in chunk])
        except Exception as exc:  # leave the rows empty; the next run retries them
            log.warning("embedding batch failed: %s", exc)
            stats["failed"] += len(chunk)
        else:
            for oid, vec in zip(chunk, vecs, strict=True):
                session.execute(
                    update(OpportunityCardRow)
                    .where(OpportunityCardRow.opportunity_id == oid)
                    .values({column: vec})
                )
            session.commit()
            stats["embedded"] += len(chunk)
        stats["cost_usd"] = (embedder.tokens - start) * price_per_m / 1e6
    return stats
