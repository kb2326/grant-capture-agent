import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from db.models import CompanyRow, OpportunityCardRow, PreferenceRow

pytestmark = pytest.mark.db


def test_card_tsv_is_computed_and_vectors_are_optional(db_session, make_opp):
    o = make_opp()
    db_session.add(
        OpportunityCardRow(
            opportunity_id=o.id, text="grid-forming inverter controls", text_hash="h"
        )
    )
    db_session.commit()
    n = db_session.scalar(
        text(
            "select count(*) from opportunity_cards "
            "where tsv @@ websearch_to_tsquery('english', 'inverter')"
        )
    )
    assert n == 1


def test_preference_is_unique_per_company_kind_value(db_session):
    co = CompanyRow(name="X", profile={})
    db_session.add(co)
    db_session.commit()
    for _ in range(2):
        db_session.add(
            PreferenceRow(
                company_id=co.id,
                kind="exclude_agency",
                value="defense",
                source="plan_edit",
            )
        )
    with pytest.raises(IntegrityError):
        db_session.commit()


def test_preference_kind_is_checked(db_session):
    co = CompanyRow(name="Y", profile={})
    db_session.add(co)
    db_session.commit()
    db_session.add(
        PreferenceRow(company_id=co.id, kind="colour", value="x", source="t")
    )
    with pytest.raises(IntegrityError):
        db_session.commit()
