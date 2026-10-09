import uuid

import pytest

from db.models import ChunkRow, DocumentRow, OpportunityRow
from evals.sample import draw_sample

pytestmark = pytest.mark.db


def _opp(db_session, source, agency, i, text):
    o = OpportunityRow(
        id=uuid.uuid4(),
        source=source,
        source_id=f"{source}-{i}",
        kind="grant",
        title=f"t{i}",
        agency=agency,
        summary=text if source == "sam_gov" else "",
        url="u",
        status="open",
        naics=[],
        assistance_listings=[],
        eligibility_codes=[],
        raw={},
        content_hash="h",
    )
    db_session.add(o)
    db_session.flush()
    if source == "grants_gov":
        d = DocumentRow(
            opportunity_id=o.id,
            corpus="solicitation",
            gcs_uri="file:///x",
            mime="text/html",
            title="d",
            sha256=str(i),
            parse_status="parsed",
            page_count=i % 7 + 1,
        )
        db_session.add(d)
        db_session.flush()
        db_session.add(
            ChunkRow(
                document_id=d.id,
                ord=1,
                page_start=1,
                page_end=1,
                text=text,
                n_tokens=10,
            )
        )


def _corpus(db_session):
    for i in range(60):
        text = (
            "Only nonprofit organizations may apply."
            if i % 4 == 0
            else "Grid storage research."
        )
        _opp(db_session, "grants_gov", f"AG{i % 12}", i, text)
    for i in range(30):
        _opp(
            db_session,
            "sam_gov",
            f"DOD{i % 6}",
            i,
            "Phase II only" if i % 3 == 0 else "battery research",
        )
    db_session.commit()


def test_sample_is_deterministic_stratified_and_capped(db_session):
    _corpus(db_session)
    a = draw_sample(db_session, seed=20261009)
    b = draw_sample(db_session, seed=20261009)
    assert [i["opportunity_id"] for i in a["items"]] == [
        i["opportunity_id"] for i in b["items"]
    ]
    sources = [i["source"] for i in a["items"]]
    assert sources.count("grants_gov") == 28 and sources.count("sam_gov") == 12
    agencies = [i["agency"] for i in a["items"]]
    assert max(agencies.count(x) for x in set(agencies)) <= 4
    assert sum(i["requirements"] for i in a["items"]) == 10
    assert all(i["source"] == "grants_gov" for i in a["items"] if i["requirements"])
    assert "prefilter" not in str(a["items"])
