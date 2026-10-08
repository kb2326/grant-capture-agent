from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import func, select

from db.models import DocumentRow, IngestRunRow, OpportunityRow
from ingest.models import AttachmentRef, Opportunity, OppStatus
from ingest.pipeline import run_ingest
from ingest.storage import LocalBlobStore

pytestmark = pytest.mark.db


def opp(source_id: str, title: str = "Grid storage", attachments=None) -> Opportunity:
    return Opportunity(
        source="grants_gov",
        source_id=source_id,
        kind="grant",
        title=title,
        status=OppStatus.open,
        description="d",
        agency="DOE",
        source_url=f"https://x/{source_id}",
        attachments=attachments or [],
    )


class FakeAdapter:
    name = "grants_gov"

    def __init__(self, opps: list[Opportunity]) -> None:
        self.opps = opps

    def iter_opportunities(self, limit=None) -> Iterator[Opportunity]:
        yield from self.opps[:limit]


class FakeFetch:
    def __init__(self, files: dict[str, bytes | None]) -> None:
        self.files, self.calls = files, []

    def __call__(self, url: str) -> bytes | None:
        self.calls.append(url)
        if url == "https://f/boom.pdf":
            raise RuntimeError("network down")
        return self.files.get(url)


PDF = AttachmentRef(
    url="https://f/a.pdf", file_name="a.pdf", mime_type="application/pdf"
)
ZIP = AttachmentRef(
    url="https://f/all.zip", file_name="all.zip", mime_type="application/zip"
)
BIG = AttachmentRef(
    url="https://f/big.pdf", file_name="big.pdf", mime_type="application/pdf"
)


def test_first_run_inserts_and_stores(db_session, tmp_path: Path):
    fetch = FakeFetch({"https://f/a.pdf": b"%PDF-a", "https://f/big.pdf": None})
    stats = run_ingest(
        FakeAdapter([opp("1", attachments=[PDF, ZIP, BIG])]),
        db_session,
        LocalBlobStore(tmp_path),
        fetch,
    )
    assert (stats.new, stats.attachments_stored, stats.attachments_skipped) == (1, 1, 2)
    assert fetch.calls == ["https://f/a.pdf", "https://f/big.pdf"]  # zip never fetched
    doc = db_session.scalars(select(DocumentRow)).one()
    assert doc.parse_status == "pending" and doc.corpus == "solicitation"
    assert (tmp_path / "raw/grants_gov/1/a.pdf").read_bytes() == b"%PDF-a"
    assert db_session.scalar(select(func.count()).select_from(IngestRunRow)) == 1


def test_rerun_is_idempotent_and_updates_in_place(db_session, tmp_path: Path):
    fetch = FakeFetch({"https://f/a.pdf": b"%PDF-a"})
    store = LocalBlobStore(tmp_path)
    run_ingest(FakeAdapter([opp("1", attachments=[PDF])]), db_session, store, fetch)
    again = run_ingest(
        FakeAdapter([opp("1", attachments=[PDF])]), db_session, store, fetch
    )
    assert (again.unchanged, again.new, again.updated) == (1, 0, 0)
    assert fetch.calls == ["https://f/a.pdf"]  # not re-downloaded
    changed = run_ingest(
        FakeAdapter([opp("1", title="Grid storage v2", attachments=[PDF])]),
        db_session,
        store,
        fetch,
    )
    assert changed.updated == 1 and changed.attachments_duplicate == 1
    assert db_session.scalar(select(func.count()).select_from(OpportunityRow)) == 1
    assert db_session.scalar(select(OpportunityRow.title)) == "Grid storage v2"
    assert db_session.scalar(select(func.count()).select_from(DocumentRow)) == 1


def test_one_bad_record_does_not_stop_the_run(db_session, tmp_path: Path):
    boom = AttachmentRef(
        url="https://f/boom.pdf", file_name="boom.pdf", mime_type="application/pdf"
    )
    stats = run_ingest(
        FakeAdapter([opp("1", attachments=[boom]), opp("2")]),
        db_session,
        LocalBlobStore(tmp_path),
        FakeFetch({}),
    )
    assert stats.new == 2 and stats.failed == 0 and len(stats.errors) == 1
    assert "boom.pdf" in stats.errors[0]
