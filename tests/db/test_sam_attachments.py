# tests/db/test_sam_attachments.py
import uuid
from datetime import date
from pathlib import Path

import httpx
import pytest
import respx
from sqlalchemy import select

from db.models import DocumentRow, OpportunityRow
from ingest.http import build_client
from ingest.sam_attachments import attach_sam_documents
from ingest.sources.sam_gov import SAM_URL, SamGovAdapter, SamQuota
from ingest.storage import LocalBlobStore

pytestmark = pytest.mark.db


@respx.mock
def test_attach_sam_documents_uses_real_file_names(db_session, tmp_path: Path):
    db_session.add(
        OpportunityRow(
            id=uuid.uuid4(),
            source="sam_gov",
            source_id="n-1",
            kind="sbir",
            title="t",
            agency="DOD",
            summary="",
            url="u",
            status="open",
            naics=[],
            assistance_listings=[],
            eligibility_codes=[],
            raw={},
            content_hash="h",
        )
    )
    db_session.commit()
    link = "https://sam.gov/api/prod/opps/v3/opportunities/resources/files/f1/download"
    respx.get(SAM_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "totalRecords": 1,
                "opportunitiesData": [
                    {"noticeId": "n-1", "title": "t", "resourceLinks": [link]}
                ],
            },
        )
    )
    respx.get(link).mock(
        return_value=httpx.Response(
            200,
            content=b"%PDF-1.7 sol",
            headers={
                "content-disposition": 'attachment; filename="Solicitation.pdf"',
                "content-type": "application/octet-stream",
            },
        )
    )
    store, day = LocalBlobStore(tmp_path), date(2026, 10, 9)
    with build_client() as c:
        adapter = SamGovAdapter(
            c, "k", request_budget=3, today=day, quota=SamQuota(store, day)
        )
        stats = attach_sam_documents(
            db_session, adapter, c, store, ["n-1"], max_bytes=10_000
        )
    assert stats == {"notices": 1, "stored": 1, "skipped": 0, "unavailable": 0}
    doc = db_session.scalars(select(DocumentRow)).one()
    assert doc.title == "Solicitation.pdf" and doc.parse_status == "pending"
