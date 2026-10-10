"""Hybrid search over document chunks of one corpus (company documents for Draft). Same RRF pattern as rag/search.py."""

import uuid
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.orm import Session

from rag.search import RRF_K, _vector_literal


@dataclass
class ChunkHit:
    chunk_id: uuid.UUID
    document_title: str
    section_path: str
    text: str
    score: float


_SQL = """
WITH f AS (
  SELECT c.id, c.embedding AS emb, c.tsv FROM chunks c JOIN documents d ON d.id = c.document_id
  WHERE d.corpus = :corpus
),
dense AS (
  SELECT id, row_number() OVER (ORDER BY emb <=> CAST(:qvec AS vector)) AS r FROM f WHERE emb IS NOT NULL
  ORDER BY emb <=> CAST(:qvec AS vector) LIMIT :depth
),
q AS (SELECT websearch_to_tsquery('english', :qtext) AS q),
sparse AS (
  SELECT id, row_number() OVER (ORDER BY ts_rank_cd(tsv, q.q) DESC) AS r FROM f, q
  WHERE tsv @@ q.q ORDER BY ts_rank_cd(tsv, q.q) DESC LIMIT :depth
),
fused AS (
  SELECT id, COALESCE(1.0 / (:rrf_k + dense.r), 0) + COALESCE(1.0 / (:rrf_k + sparse.r), 0) AS score
  FROM dense FULL OUTER JOIN sparse USING (id)
)
SELECT fused.id, d.title, c.section_path, c.text, fused.score
FROM fused JOIN chunks c ON c.id = fused.id JOIN documents d ON d.id = c.document_id
ORDER BY fused.score DESC, fused.id LIMIT :k
"""


def search_chunks(
    session: Session,
    *,
    query_text: str,
    query_vec: list[float],
    corpus: str = "company",
    k: int = 8,
    depth: int = 50,
) -> list[ChunkHit]:
    rows = session.execute(
        text(_SQL),
        {
            "corpus": corpus,
            "qvec": _vector_literal(query_vec),
            "qtext": query_text,
            "depth": depth,
            "k": k,
            "rrf_k": RRF_K,
        },
    )
    return [ChunkHit(r[0], r[1], r[2], r[3], float(r[4])) for r in rows]
