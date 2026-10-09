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
    version = "fake/1"

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
    stored = list((tmp_path / "raw/grants_gov/1").glob("*-a.pdf"))
    assert len(stored) == 1 and stored[0].read_bytes() == b"%PDF-a"
    assert db_session.scalar(select(func.count()).select_from(IngestRunRow)) == 1
    row = db_session.scalars(select(OpportunityRow)).one()
    assert row.adapter_version == "fake/1" and row.fetched_at is not None


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


def test_full_run_records_quality_issues(db_session, tmp_path: Path):
    stats = run_ingest(
        FakeAdapter([]), db_session, LocalBlobStore(tmp_path), FakeFetch({})
    )
    assert any(
        i["check"] == "Q1_empty" and i["severity"] == "error"
        for i in stats.quality_issues
    )
    run = db_session.scalars(select(IngestRunRow)).one()
    assert (
        run.stats["quality_issues"][0]["check"] == "Q1_empty"
        and run.stats["limit"] is None
    )


class ExplodingAdapter(FakeAdapter):
    def iter_opportunities(self, limit=None) -> Iterator[Opportunity]:
        yield opp("1")
        raise RuntimeError("source went away")


def test_adapter_crash_still_records_the_run(db_session, tmp_path: Path):
    stats = run_ingest(
        ExplodingAdapter([]), db_session, LocalBlobStore(tmp_path), FakeFetch({})
    )
    assert stats.new == 1 and stats.aborted
    run = db_session.scalars(select(IngestRunRow)).one()
    assert run.stats["aborted"] is True


def test_adapter_item_errors_count_as_failed(db_session, tmp_path: Path):
    adapter = FakeAdapter([opp("1")])
    adapter.errors = ["grants_gov:x: HTTP 404"]
    stats = run_ingest(adapter, db_session, LocalBlobStore(tmp_path), FakeFetch({}))
    assert stats.failed == 1 and any("HTTP 404" in e for e in stats.errors)


def test_colliding_attachment_names_are_stored_separately(db_session, tmp_path: Path):
    a1 = AttachmentRef(
        url="https://f/x1", file_name="a b.pdf", mime_type="application/pdf"
    )
    a2 = AttachmentRef(
        url="https://f/x2", file_name="a_b.pdf", mime_type="application/pdf"
    )
    fetch = FakeFetch({"https://f/x1": b"%PDF-one", "https://f/x2": b"%PDF-two"})
    stats = run_ingest(
        FakeAdapter([opp("1", attachments=[a1, a2])]),
        db_session,
        LocalBlobStore(tmp_path),
        fetch,
    )
    assert stats.attachments_stored == 2
    docs = db_session.scalars(select(DocumentRow)).all()
    assert len({d.gcs_uri for d in docs}) == 2


class FlakyFetch:
    """Fails the first time each URL is fetched, then succeeds."""

    def __init__(self, data: bytes) -> None:
        self.data, self.seen = data, set()

    def __call__(self, url: str) -> bytes | None:
        if url not in self.seen:
            self.seen.add(url)
            raise RuntimeError("timeout")
        return self.data


def test_failed_attachment_is_retried_on_the_next_run(db_session, tmp_path: Path):
    flaky = AttachmentRef(
        url="https://f/nofo.pdf", file_name="nofo.pdf", mime_type="application/pdf"
    )
    store, fetch = LocalBlobStore(tmp_path), FlakyFetch(b"%PDF-nofo")
    first = run_ingest(
        FakeAdapter([opp("1", attachments=[flaky])]), db_session, store, fetch
    )
    assert first.attachments_stored == 0 and len(first.errors) == 1
    second = run_ingest(
        FakeAdapter([opp("1", attachments=[flaky])]), db_session, store, fetch
    )
    assert second.attachments_stored == 1
    assert db_session.scalar(select(func.count()).select_from(DocumentRow)) == 1
