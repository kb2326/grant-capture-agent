import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from db.models import DocumentRow, OpportunityRow
from ingest.descriptions import store_descriptions
from ingest.storage import LocalBlobStore, read_uri

pytestmark = pytest.mark.db


def _opp(db_session, summary: str) -> OpportunityRow:
    o = OpportunityRow(
        id=uuid.uuid4(),
        source="sam_gov",
        source_id=f"n-{uuid.uuid4().hex[:6]}",
        kind="contract",
        title="BAA",
        agency="DARPA",
        summary=summary,
        url="u",
        status="open",
        naics=[],
        assistance_listings=[],
        eligibility_codes=[],
        raw={},
        content_hash="h",
    )
    db_session.add(o)
    db_session.commit()
    return o


def test_description_becomes_a_pending_document_once(db_session, tmp_path: Path):
    o = _opp(db_session, "<p>Only small businesses may respond.</p>")
    store = LocalBlobStore(tmp_path)
    assert store_descriptions(db_session, store, [o.id]) == {"stored": 1, "skipped": 0}
    assert store_descriptions(db_session, store, [o.id]) == {"stored": 0, "skipped": 1}
    doc = db_session.scalars(select(DocumentRow)).one()
    assert (
        doc.title == "notice-description.html"
        and doc.parse_status == "pending"
        and doc.mime == "text/html"
    )
    assert b"Only small businesses may respond." in read_uri(doc.gcs_uri)


def test_empty_description_is_skipped(db_session, tmp_path: Path):
    o = _opp(db_session, "   ")
    assert store_descriptions(db_session, LocalBlobStore(tmp_path), [o.id]) == {
        "stored": 0,
        "skipped": 1,
    }
