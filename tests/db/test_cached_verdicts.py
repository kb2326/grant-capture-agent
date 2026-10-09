import pytest

from app.discover.checker import cached_verdicts
from db.models import CompanyRow, EligibilityVerdictRow

pytestmark = pytest.mark.db


def test_cached_verdicts_for_company(db_session, make_opp):
    co = CompanyRow(name="Z", profile={})
    db_session.add(co)
    db_session.commit()
    a, b = make_opp(), make_opp()
    db_session.add(
        EligibilityVerdictRow(
            opportunity_id=a.id,
            company_id=co.id,
            verdict="INELIGIBLE",
            detail={},
            rules_version="r",
        )
    )
    db_session.commit()
    assert cached_verdicts(db_session, co.id, [a.id, b.id]) == {a.id: "INELIGIBLE"}
