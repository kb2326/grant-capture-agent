import uuid
from datetime import date

import pytest

from db.models import IngestRunRow, OpportunityRow
from ingest.quality import check_run, previous_full_run_seen

pytestmark = pytest.mark.db


def _ids(issues):
    return {i.check for i in issues}


def _opp(source_id: str, close: date | None) -> OpportunityRow:
    return OpportunityRow(
        id=uuid.uuid4(),
        source="grants_gov",
        source_id=source_id,
        kind="grant",
        title="t",
        agency="a",
        summary="",
        url="u",
        status="open",
        close_at=close,
        naics=[],
        assistance_listings=[],
        eligibility_codes=[],
        raw={},
        content_hash="h",
    )


def test_empty_run_is_an_error(db_session):
    assert "Q1_empty" in _ids(
        check_run(db_session, "grants_gov", seen=0, failed=0, previous_seen=None)
    )


def test_volume_drop_against_previous_full_run(db_session):
    db_session.add(
        IngestRunRow(stats={"source": "grants_gov", "limit": None, "seen": 100})
    )
    db_session.add(
        IngestRunRow(stats={"source": "grants_gov", "limit": 10, "seen": 10})
    )  # ignored: partial
    db_session.commit()
    prev = previous_full_run_seen(db_session, "grants_gov")
    assert prev == 100
    assert "Q2_volume_drop" in _ids(
        check_run(db_session, "grants_gov", seen=50, failed=0, previous_seen=prev)
    )
    assert "Q2_volume_drop" not in _ids(
        check_run(db_session, "grants_gov", seen=80, failed=0, previous_seen=prev)
    )


def test_error_rate(db_session):
    assert "Q3_error_rate" in _ids(
        check_run(db_session, "grants_gov", seen=100, failed=10, previous_seen=None)
    )
    assert "Q3_error_rate" not in _ids(
        check_run(db_session, "grants_gov", seen=100, failed=5, previous_seen=None)
    )


def test_missing_close_dates_warning(db_session):
    db_session.add_all(
        [_opp(str(i), date(2026, 12, 1)) for i in range(8)]
        + [_opp("x", None), _opp("y", None)]
    )
    db_session.commit()
    issues = check_run(db_session, "grants_gov", seen=10, failed=0, previous_seen=None)
    q4 = [i for i in issues if i.check == "Q4_missing_close_dates"]
    assert q4 and q4[0].severity == "warning"
