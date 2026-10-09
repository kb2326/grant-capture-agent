from datetime import date

import pytest

from db.models import OpportunityCardRow
from rag.search import Filters, hybrid_search

pytestmark = pytest.mark.db


def _vec(i: int) -> list[float]:
    v = [0.0] * 768
    v[i] = 1.0
    return v


@pytest.fixture
def cards(db_session, make_opp):
    a = make_opp(title="A", agency="DEPT OF ENERGY > ARPA-E", kind="sbir")
    b = make_opp(
        title="B", agency="DEPT OF DEFENSE > DEPT OF THE ARMY", kind="contract"
    )
    c = make_opp(title="C", status="closed")
    d = make_opp(title="D", close_at=date(2026, 10, 15), award_ceiling=10_000)
    e = make_opp(title="E")  # card but no embedding yet
    rows = [
        (a, "grid-forming inverter controls", _vec(0)),
        (b, "battery degradation modeling", _vec(1)),
        (c, "inverter for closed call", _vec(0)),
        (d, "inverter closing soon", _vec(2)),
        (e, "solid-state battery management inverter", None),
    ]
    for o, text, vec in rows:
        db_session.add(
            OpportunityCardRow(
                opportunity_id=o.id, text=text, text_hash="h", emb_local=vec
            )
        )
    db_session.commit()
    return {"a": a.id, "b": b.id, "c": c.id, "d": d.id, "e": e.id}


def _ids(hits):
    return [h.opportunity_id for h in hits]


def _search(session, q, vec, **filters):
    return hybrid_search(
        session,
        query_text=q,
        query_vec=vec,
        column="emb_local",
        filters=Filters(**filters),
    )


def test_hit_in_both_lists_scores_sum_of_reciprocal_ranks(db_session, cards):
    hits = _search(db_session, "grid-forming", _vec(0))
    assert hits[0].opportunity_id == cards["a"]
    assert hits[0].score == pytest.approx(1 / 61 + 1 / 61)


def test_dense_only_query_and_stopword_query_still_return(db_session, cards):
    for q in ("zzzqqq", "the of", '"battery" -"solar"'):
        hits = _search(db_session, q, _vec(1))
        assert hits[0].opportunity_id == cards["b"], q


def test_card_without_embedding_is_found_by_keywords(db_session, cards):
    hits = _search(db_session, "solid-state battery", _vec(5))
    assert cards["e"] in _ids(hits)


def test_filters_status_kind_close_award_and_loose_agency(db_session, cards):
    ids = _ids(
        _search(
            db_session,
            "inverter battery",
            _vec(0),
            min_close=date(2026, 11, 1),
            exclude_agencies=["defense"],
        )
    )
    assert cards["c"] not in ids and cards["d"] not in ids
    assert cards["b"] not in ids and cards["a"] in ids
    assert _ids(_search(db_session, "inverter", _vec(0), kinds=["sbir"])) == [
        cards["a"]
    ]
    ids = _ids(_search(db_session, "inverter", _vec(0), award_min=50_000))
    assert cards["d"] not in ids


def test_unknown_column_is_rejected(db_session):
    with pytest.raises(ValueError):
        hybrid_search(
            db_session,
            query_text="x",
            query_vec=_vec(0),
            column="text; drop table x",
            filters=Filters(),
        )
