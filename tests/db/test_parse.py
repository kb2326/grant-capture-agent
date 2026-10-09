import uuid
from pathlib import Path

import pytest
from fpdf import FPDF
from sqlalchemy import func, select

from db.models import ChunkRow, DocumentRow, OpportunityRow
from ingest.parsing import parse_documents
from ingest.storage import LocalBlobStore, read_uri

pytestmark = pytest.mark.db


def _pdf(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)
    pdf.multi_cell(0, 6, text)
    pdf.add_page()
    return bytes(pdf.output())


def _setup(db_session, tmp_path: Path) -> uuid.UUID:
    store = LocalBlobStore(tmp_path)
    opp = OpportunityRow(
        id=uuid.uuid4(),
        source="grants_gov",
        source_id="p1",
        kind="grant",
        title="t",
        agency="a",
        summary="",
        url="u",
        status="open",
        naics=[],
        assistance_listings=[],
        eligibility_codes=[],
        raw={},
        content_hash="h",
    )
    db_session.add(opp)
    db_session.flush()
    files = [
        (
            "nofo.pdf",
            "application/pdf",
            _pdf("Eligible applicants are small business concerns only. " * 2),
        ),
        (
            "page.html",
            "text/html",
            b"<h2>Eligibility</h2><p>State governments only may apply for this program.</p>",
        ),
        ("old.doc", "application/msword", b"\xd0\xcf\x11\xe0"),
    ]
    for name, mime, data in files:
        uri = store.put(f"raw/grants_gov/p1/{name}", data)
        db_session.add(
            DocumentRow(
                opportunity_id=opp.id,
                corpus="solicitation",
                gcs_uri=uri,
                mime=mime,
                title=name,
                sha256=name,
                parse_status="pending",
            )
        )
    db_session.commit()
    return opp.id


def test_parse_sets_status_and_writes_page_chunks(db_session, tmp_path: Path):
    _setup(db_session, tmp_path)
    stats = parse_documents(db_session, read_uri)
    assert stats == {"parsed": 2, "no_text_layer": 0, "unsupported": 1, "failed": 0}
    pdf = db_session.scalars(
        select(DocumentRow).where(DocumentRow.title == "nofo.pdf")
    ).one()
    assert pdf.page_count == 2
    chunks = db_session.scalars(
        select(ChunkRow).where(ChunkRow.document_id == pdf.id).order_by(ChunkRow.ord)
    ).all()
    assert [c.page_start for c in chunks] == [
        1,
        2,
    ] and "small business concerns" in chunks[0].text


def test_parse_is_idempotent(db_session, tmp_path: Path):
    _setup(db_session, tmp_path)
    parse_documents(db_session, read_uri)
    before = db_session.scalar(select(func.count()).select_from(ChunkRow))
    assert parse_documents(db_session, read_uri) == {
        "parsed": 0,
        "no_text_layer": 0,
        "unsupported": 0,
        "failed": 0,
    }
    assert db_session.scalar(select(func.count()).select_from(ChunkRow)) == before
