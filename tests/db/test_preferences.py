import pytest

from app.contracts import Preference
from app.memory import load_preferences, save_preferences
from db.models import CompanyRow

pytestmark = pytest.mark.db


def test_saved_and_profile_preferences_load_together_without_duplicates(db_session):
    co = CompanyRow(
        name="P",
        profile={
            "preferences": {"min_award_usd": 50000, "exclude_agencies": ["defense"]}
        },
    )
    db_session.add(co)
    db_session.commit()
    prefs = [
        Preference(kind="exclude_agency", value="defense"),
        Preference(kind="avoid_topic", value="furniture"),
    ]
    assert save_preferences(db_session, co.id, prefs, source="plan_edit") == 2
    assert save_preferences(db_session, co.id, prefs, source="plan_edit") == 0
    loaded = load_preferences(db_session, co.id)
    assert sorted((p.kind, p.value) for p in loaded) == [
        ("avoid_topic", "furniture"),
        ("exclude_agency", "defense"),
        ("min_award_usd", "50000"),
    ]
