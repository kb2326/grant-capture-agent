"""Store an opportunity's description as a document, so notices without attachments can be analyzed.

Many SAM.gov notices put the whole solicitation (eligibility included) in the description field of the
daily extract. Storing it as `notice-description.html` gives it page/section citations like any document.
"""

import hashlib
import uuid
from html import escape

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import DocumentRow, OpportunityRow
from ingest.storage import BlobStore, safe_key

FILE_NAME = "notice-description.html"


def store_descriptions(
    session: Session, store: BlobStore, opportunity_ids: list[uuid.UUID]
) -> dict[str, int]:
    stats = {"stored": 0, "skipped": 0}
    for opp_id in opportunity_ids:
        opp = session.get(OpportunityRow, opp_id)
        summary = (opp.summary or "").strip() if opp else ""
        already = opp is not None and session.scalar(
            select(DocumentRow.id).where(
                DocumentRow.opportunity_id == opp_id, DocumentRow.title == FILE_NAME
            )
        )
        if not summary or already:
            stats["skipped"] += 1
            continue
        body = summary if "<" in summary else f"<p>{escape(summary)}</p>"
        data = f"<html><body><h1>{escape(opp.title)}</h1>{body}</body></html>".encode()
        sha = hashlib.sha256(data).hexdigest()
        uri = store.put(safe_key(opp.source, opp.source_id, FILE_NAME), data)
        session.add(
            DocumentRow(
                opportunity_id=opp_id,
                corpus="solicitation",
                gcs_uri=uri,
                mime="text/html",
                title=FILE_NAME,
                sha256=sha,
                parse_status="pending",
            )
        )
        session.commit()
        stats["stored"] += 1
    return stats
