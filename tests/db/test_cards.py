import pytest

from db.models import OpportunityCardRow
from rag.card import build_cards

pytestmark = pytest.mark.db


def test_build_cards_creates_then_updates_only_changed(db_session, make_opp):
    a = make_opp(title="A")
    make_opp(title="B")
    assert build_cards(db_session) == {"created": 2, "updated": 0, "unchanged": 0}
    card = db_session.get(OpportunityCardRow, a.id)
    card.emb_gemini = [0.1] * 768
    a.summary = "changed"
    db_session.commit()
    assert build_cards(db_session) == {"created": 0, "updated": 1, "unchanged": 1}
    db_session.expire_all()
    # changed text must be re-embedded
    assert db_session.get(OpportunityCardRow, a.id).emb_gemini is None
