"""Rerank fused hits with the Vertex AI Ranking API; any failure falls back to fused order. M2 spec §3.4."""

import logging
from dataclasses import dataclass
from typing import Protocol

from app.config import Settings

log = logging.getLogger(__name__)
MAX_RECORD_CHARS = 2_000  # the ranker reads ~512 tokens per record


@dataclass
class RerankDoc:
    id: str
    title: str
    content: str


class Reranker(Protocol):
    name: str
    calls: int

    def rerank(
        self, query: str, docs: list[RerankDoc]
    ) -> list[tuple[str, float]] | None: ...


class NoRerank:
    name = "none"
    calls = 0

    def rerank(
        self, query: str, docs: list[RerankDoc]
    ) -> list[tuple[str, float]] | None:
        return None


class VertexRanker:
    name = "vertex"

    def __init__(self, settings: Settings, client=None) -> None:
        if client is None:
            from google.cloud import discoveryengine_v1 as de

            client = de.RankServiceClient()
        self.client, self.model, self.calls = client, settings.rerank_model, 0
        self.config = (
            f"projects/{settings.google_cloud_project}/locations/global"
            "/rankingConfigs/default_ranking_config"
        )

    def rerank(
        self, query: str, docs: list[RerankDoc]
    ) -> list[tuple[str, float]] | None:
        if not docs:
            return []
        from google.cloud import discoveryengine_v1 as de

        request = de.RankRequest(
            ranking_config=self.config,
            model=self.model,
            top_n=len(docs),
            query=query,
            records=[
                de.RankingRecord(
                    id=d.id, title=d.title, content=d.content[:MAX_RECORD_CHARS]
                )
                for d in docs
            ],
        )
        self.calls += 1  # billed even when the call fails
        try:
            response = self.client.rank(request=request)
        except Exception as exc:  # a request never fails because of reranking
            log.warning("rerank failed, keeping fused order: %s", exc)
            return None
        return [(r.id, float(r.score)) for r in response.records]


def make_reranker(enabled: bool, settings: Settings) -> Reranker:
    return VertexRanker(settings) if enabled else NoRerank()
