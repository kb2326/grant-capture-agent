"""Hybrid search: dense (pgvector cosine) + sparse (Postgres full text), fused with RRF in one statement.

M2 spec §3.3. With ~2,700 cards Postgres scans the filtered set rather than using the HNSW index,
which is fine at this size.
"""

import uuid
from dataclasses import dataclass, field
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from rag.embed import COLUMNS

RRF_K = 60


@dataclass
class Filters:
    kinds: list[str] = field(default_factory=list)
    statuses: list[str] = field(default_factory=lambda: ["open", "forecasted"])
    min_close: date | None = None  # null close dates always pass
    exclude_agencies: list[str] = field(
        default_factory=list
    )  # case-insensitive substrings
    award_min: float | None = None  # null award ceilings always pass


@dataclass
class Hit:
    opportunity_id: uuid.UUID
    score: float
    dense_rank: int | None
    sparse_rank: int | None


_SQL = """
WITH f AS (
  SELECT c.opportunity_id, c.{col} AS emb, c.tsv
  FROM opportunity_cards c JOIN opportunities o ON o.id = c.opportunity_id
  WHERE o.status = ANY(CAST(:statuses AS text[]))
    AND (cardinality(CAST(:kinds AS text[])) = 0 OR o.kind = ANY(CAST(:kinds AS text[])))
    AND (CAST(:min_close AS date) IS NULL OR o.close_at IS NULL OR o.close_at >= CAST(:min_close AS date))
    AND (CAST(:award_min AS numeric) IS NULL OR o.award_ceiling IS NULL
         OR o.award_ceiling >= CAST(:award_min AS numeric))
    AND NOT EXISTS (SELECT 1 FROM unnest(CAST(:exclude AS text[])) x WHERE o.agency ILIKE '%' || x || '%')
),
dense AS (
  SELECT opportunity_id, row_number() OVER (ORDER BY emb <=> CAST(:qvec AS vector)) AS r
  FROM f WHERE emb IS NOT NULL
  ORDER BY emb <=> CAST(:qvec AS vector) LIMIT :depth
),
q AS (SELECT websearch_to_tsquery('english', :qtext) AS q),
sparse AS (
  SELECT opportunity_id, row_number() OVER (ORDER BY ts_rank_cd(tsv, q.q) DESC) AS r
  FROM f, q WHERE tsv @@ q.q
  ORDER BY ts_rank_cd(tsv, q.q) DESC LIMIT :depth
)
SELECT opportunity_id,
       COALESCE(1.0 / (:rrf_k + dense.r), 0) + COALESCE(1.0 / (:rrf_k + sparse.r), 0) AS score,
       dense.r AS dense_rank, sparse.r AS sparse_rank
FROM dense FULL OUTER JOIN sparse USING (opportunity_id)
ORDER BY score DESC, opportunity_id
LIMIT :k
"""


def _vector_literal(vec: list[float]) -> str:
    return "[" + ",".join(f"{x:.7f}" for x in vec) + "]"


def hybrid_search(
    session: Session,
    *,
    query_text: str,
    query_vec: list[float],
    column: str,
    filters: Filters,
    k: int = 30,
    depth: int = 50,
) -> list[Hit]:
    # the column name is formatted into SQL, so it must be whitelisted
    if column not in COLUMNS.values():
        raise ValueError(f"unknown embedding column {column!r}")
    rows = session.execute(
        text(_SQL.format(col=column)),
        {
            "statuses": filters.statuses,
            "kinds": filters.kinds,
            "min_close": filters.min_close,
            "award_min": filters.award_min,
            "exclude": filters.exclude_agencies,
            "qvec": _vector_literal(query_vec),
            "qtext": query_text,
            "depth": depth,
            "k": k,
            "rrf_k": RRF_K,
        },
    )
    return [
        Hit(r.opportunity_id, float(r.score), r.dense_rank, r.sparse_rank) for r in rows
    ]
