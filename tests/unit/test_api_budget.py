from api.budget import SessionBudget
from api.cache import ResultCache
from app.config import Settings


def test_budget_allows_until_limit_and_ignores_negative():
    b = SessionBudget(0.10)
    assert b.allows()
    b.add(0.06)
    b.add(-1.0)
    assert b.allows() and round(b.spent_usd, 2) == 0.06
    b.add(0.05)
    assert not b.allows()


def test_cache_round_trip_and_miss():
    c = ResultCache()
    assert c.get(("analyze", "x")) is None
    c.put(("analyze", "x"), {"verdict": "ELIGIBLE"})
    assert c.get(("analyze", "x")) == {"verdict": "ELIGIBLE"}


def test_default_ui_budget():
    assert Settings(_env_file=None).ui_session_budget_usd == 0.50


def test_reserve_holds_room_and_settle_replaces_estimate():
    b = SessionBudget(0.10)
    assert b.reserve(0.08)
    assert not b.reserve(0.08)  # a concurrent second call cannot pass the cap
    b.settle(0.08, 0.03)
    assert round(b.spent_usd, 2) == 0.03 and b.reserve(0.05)
