"""Build the page-tagged text layer for stored documents (M1 spec §3.1)."""

import uuid
from collections.abc import Callable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from db.models import ChunkRow, DocumentRow
from ingest.textlayer import extract_pages


def parse_documents(
    session: Session,
    read: Callable[[str], bytes],
    *,
    limit: int | None = None,
    opportunity_id: uuid.UUID | None = None,
) -> dict[str, int]:
    stats = {"parsed": 0, "no_text_layer": 0, "unsupported": 0, "failed": 0}
    q = (
        select(DocumentRow)
        .where(DocumentRow.parse_status == "pending")
        .order_by(DocumentRow.created_at)
    )
    if opportunity_id is not None:
        q = q.where(DocumentRow.opportunity_id == opportunity_id)
    if limit is not None:
        q = q.limit(limit)
    for doc in session.scalars(q).all():
        try:
            pages = extract_pages(read(doc.gcs_uri), doc.mime, doc.title)
        except Exception as exc:  # one bad file must not stop the run
            doc.parse_status, doc.parse_error = (
                "failed",
                f"{type(exc).__name__}: {exc}"[:500],
            )
            stats["failed"] += 1
            session.commit()
            continue
        if pages is None:
            doc.parse_status = "unsupported"
            stats["unsupported"] += 1
            session.commit()
            continue
        session.execute(delete(ChunkRow).where(ChunkRow.document_id == doc.id))
        for p in pages:
            session.add(
                ChunkRow(
                    document_id=doc.id,
                    ord=p.number,
                    section_path=p.heading,
                    page_start=p.number,
                    page_end=p.number,
                    text=p.text,
                    n_tokens=len(p.text) // 4,
                )
            )
        doc.page_count = len(pages)
        doc.parse_status = (
            "parsed" if any(p.has_text for p in pages) else "no_text_layer"
        )
        stats[doc.parse_status] += 1
        session.commit()
    return stats
