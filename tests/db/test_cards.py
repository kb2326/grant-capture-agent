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


from rag.embed import embed_cards  # noqa: E402


class FakeEmbedder:
    name = "fake"

    def __init__(self, fail_on: str | None = None):
        self.tokens, self.fail_on = 0, fail_on

    def embed_documents(self, texts):
        if self.fail_on and any(self.fail_on in t for t in texts):
            raise RuntimeError("boom")
        self.tokens += len(texts)
        return [[0.5] * 768 for _ in texts]

    def embed_query(self, text):
        return [0.5] * 768


def test_embed_cards_fills_only_missing_rows(db_session, make_opp):
    for t in ("A", "B", "C"):
        make_opp(title=t)
    build_cards(db_session)
    out = embed_cards(
        db_session, FakeEmbedder(), column="emb_local", price_per_m=0.0, batch=2
    )
    assert out["embedded"] == 3 and out["failed"] == 0
    again = embed_cards(db_session, FakeEmbedder(), column="emb_local", price_per_m=0.0)
    assert again["embedded"] == 0


def test_embed_cards_stops_at_budget_and_counts_failures(db_session, make_opp):
    for t in ("A", "B", "C"):
        make_opp(title=t)
    build_cards(db_session)
    out = embed_cards(
        db_session,
        FakeEmbedder(),
        column="emb_gemini",
        price_per_m=1e6,
        max_usd=0.5,
        batch=1,
    )
    assert out["embedded"] == 1 and out["stopped"] == "budget"
    out = embed_cards(
        db_session,
        FakeEmbedder(fail_on="B |"),
        column="emb_local",
        price_per_m=0.0,
        batch=1,
    )
    assert out["embedded"] == 2 and out["failed"] == 1
