"""Fetch SAM.gov attachments for selected notices and attach them to the bulk-extract rows."""

import hashlib

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import DocumentRow, OpportunityRow
from ingest.http import download_named
from ingest.sources.sam_gov import SamGovAdapter
from ingest.storage import BlobStore, is_allowed_attachment, safe_key


def attach_sam_documents(
    session: Session,
    adapter: SamGovAdapter,
    client: httpx.Client,
    store: BlobStore,
    notice_ids: list[str],
    *,
    max_bytes: int,
) -> dict[str, int]:
    stats = {"notices": 0, "stored": 0, "skipped": 0, "unavailable": 0}
    for notice_id in notice_ids:
        row = session.scalar(
            select(OpportunityRow).where(
                OpportunityRow.source == "sam_gov",
                OpportunityRow.source_id == notice_id,
            )
        )
        record = (
            adapter.fetch_notice(notice_id, row.posted_at) if row is not None else None
        )
        if record is None:
            stats["unavailable"] += 1
            continue
        stats["notices"] += 1
        for link in record.get("resourceLinks") or []:
            try:
                data, name, ctype = download_named(client, link, max_bytes=max_bytes)
            except httpx.HTTPError:
                stats["skipped"] += 1
                continue
            name = name or link.rstrip("/").split("/")[-2]
            if data is None or not is_allowed_attachment(ctype, name):
                stats["skipped"] += 1
                continue
            sha = hashlib.sha256(data).hexdigest()
            if session.scalar(
                select(DocumentRow.id).where(
                    DocumentRow.opportunity_id == row.id, DocumentRow.sha256 == sha
                )
            ):
                continue
            uri = store.put(safe_key("sam_gov", notice_id, f"{sha[:12]}-{name}"), data)
            session.add(
                DocumentRow(
                    opportunity_id=row.id,
                    corpus="solicitation",
                    gcs_uri=uri,
                    mime=(ctype or "").split(";")[0] or None,
                    title=name,
                    sha256=sha,
                    parse_status="pending",
                )
            )
            stats["stored"] += 1
        session.commit()
    return stats
