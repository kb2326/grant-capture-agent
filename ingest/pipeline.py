"""Upsert opportunities, store their attachments, and record run statistics."""

import hashlib
import logging
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import DocumentRow, IngestRunRow, OpportunityRow
from ingest.models import Opportunity
from ingest.quality import check_run, previous_full_run_seen
from ingest.sources.base import SourceAdapter
from ingest.storage import BlobStore, is_allowed_attachment, safe_key

log = logging.getLogger(__name__)


@dataclass
class IngestStats:
    seen: int = 0
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0
    attachments_stored: int = 0
    attachments_skipped: int = 0
    attachments_duplicate: int = 0
    errors: list[str] = field(default_factory=list)
    quality_issues: list[dict] = field(default_factory=list)
    aborted: bool = False


def _apply(
    row: OpportunityRow, o: Opportunity, content_hash: str, adapter_version: str
) -> None:
    row.kind, row.title, row.agency = o.kind, o.title, o.agency
    row.summary, row.url, row.status = o.description, o.source_url, o.status.value
    row.posted_at, row.close_at = o.key_dates.post_date, o.key_dates.close_date
    row.award_floor = (
        o.funding.min_award_amount.amount if o.funding.min_award_amount else None
    )
    row.award_ceiling = (
        o.funding.max_award_amount.amount if o.funding.max_award_amount else None
    )
    row.naics, row.assistance_listings = list(o.naics), list(o.assistance_listings)
    row.eligibility_codes = list(o.accepted_applicant_types)
    now = datetime.now(UTC)
    cg = o.to_commongrants(
        record_id=row.id, created_at=row.ingested_at or now, last_modified_at=now
    )
    row.raw = cg.model_dump(mode="json", by_alias=True, exclude_none=True)
    row.content_hash = content_hash
    row.fetched_at = now
    row.raw_uri = o.raw_uri
    row.adapter_version = adapter_version


def _store_attachments(
    session: Session,
    row: OpportunityRow,
    o: Opportunity,
    store: BlobStore,
    fetch: Callable[[str], bytes | None],
    stats: IngestStats,
) -> bool:
    """Store allowed attachments. Returns True if any download failed (retry next run)."""
    failed = False
    for att in o.attachments:
        if not is_allowed_attachment(att.mime_type, att.file_name):
            stats.attachments_skipped += 1
            continue
        try:
            data = fetch(att.url)
        except Exception as exc:  # one bad file must not stop the run
            stats.errors.append(f"{o.source}:{o.source_id}:{att.file_name}: {exc}")
            failed = True
            continue
        if data is None:
            stats.attachments_skipped += 1
            continue
        sha = hashlib.sha256(data).hexdigest()
        exists = session.scalar(
            select(DocumentRow.id).where(
                DocumentRow.opportunity_id == row.id, DocumentRow.sha256 == sha
            )
        )
        if exists:
            stats.attachments_duplicate += 1
            continue
        # The content hash makes keys unique and immutable: names that clean to the same
        # string, or a revised file under the same name, never overwrite each other.
        uri = store.put(
            safe_key(o.source, o.source_id, f"{sha[:12]}-{att.file_name}"), data
        )
        session.add(
            DocumentRow(
                opportunity_id=row.id,
                corpus="solicitation",
                gcs_uri=uri,
                mime=att.mime_type,
                title=att.file_name,
                sha256=sha,
                parse_status="pending",
            )
        )
        stats.attachments_stored += 1
    return failed


def _ingest_all(
    adapter: SourceAdapter,
    session: Session,
    store: BlobStore,
    fetch: Callable[[str], bytes | None],
    limit: int | None,
    download_attachments: bool,
    stats: IngestStats,
) -> None:
    for o in adapter.iter_opportunities(limit=limit):
        stats.seen += 1
        try:
            content_hash = o.content_hash()
            row = session.scalar(
                select(OpportunityRow).where(
                    OpportunityRow.source == o.source,
                    OpportunityRow.source_id == o.source_id,
                )
            )
            if row is not None and row.content_hash == content_hash:
                stats.unchanged += 1
                continue
            if row is None:
                row = OpportunityRow(
                    id=uuid.uuid4(), source=o.source, source_id=o.source_id
                )
                session.add(row)
                stats.new += 1
            else:
                stats.updated += 1
            _apply(row, o, content_hash, getattr(adapter, "version", "unknown"))
            session.flush()
            if download_attachments:
                if _store_attachments(session, row, o, store, fetch, stats):
                    row.content_hash = "retry-attachments"  # forces a retry next run
            session.commit()
        except Exception as exc:
            session.rollback()
            stats.failed += 1
            stats.errors.append(f"{o.source}:{o.source_id}: {exc}")
            log.exception("failed to ingest %s:%s", o.source, o.source_id)


def run_ingest(
    adapter: SourceAdapter,
    session: Session,
    store: BlobStore,
    fetch: Callable[[str], bytes | None],
    *,
    limit: int | None = None,
    download_attachments: bool = True,
) -> IngestStats:
    stats = IngestStats()
    started = datetime.now(UTC)
    prev = previous_full_run_seen(session, adapter.name)
    try:
        _ingest_all(adapter, session, store, fetch, limit, download_attachments, stats)
    # If the source itself fails mid-run, keep what was loaded and still record the run.
    except Exception as exc:
        session.rollback()
        stats.aborted = True
        stats.errors.append(f"{adapter.name}: run aborted: {type(exc).__name__}: {exc}")
        log.exception("ingest run for %s aborted", adapter.name)
    for err in getattr(adapter, "errors", []):  # per-item failures inside the adapter
        stats.failed += 1
        stats.errors.append(err)
    if limit is None:
        stats.quality_issues = [
            asdict(i)
            for i in check_run(
                session,
                adapter.name,
                seen=stats.seen,
                failed=stats.failed,
                previous_seen=prev,
            )
        ]
    session.add(
        IngestRunRow(
            started_at=started,
            ended_at=datetime.now(UTC),
            stats={"source": adapter.name, "limit": limit, **asdict(stats)},
        )
    )
    session.commit()
    return stats
