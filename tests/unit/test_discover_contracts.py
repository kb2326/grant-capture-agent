import uuid
from datetime import date

from app.config import Settings
from app.contracts import Candidate, Preference, SearchPlan, SearchQuery


def test_discover_settings_defaults():
    s = Settings(_env_file=None)
    assert s.discover_v4_transport == "direct"
    assert (s.discover_k, s.discover_max_iterations, s.discover_v4_max_checks) == (
        5,
        3,
        5,
    )
    assert s.model_embedding_local == "google/embeddinggemma-2"
    assert s.discover_embedding == "gemini" and s.discover_rerank is True
    assert s.discover_eval_budget_usd <= 2.0


def test_search_plan_defaults_and_schema():
    p = SearchPlan(intent="x", queries=[SearchQuery(text="grid inverters")])
    q = p.queries[0]
    assert q.kinds == [] and q.min_days_to_close == 14 and q.award_min is None
    assert p.exclude == [] and "queries" in SearchPlan.model_json_schema()["properties"]


def test_candidate_defaults():
    c = Candidate(
        opportunity_id=uuid.uuid4(),
        source_id="s",
        title="t",
        agency="a",
        status="open",
        close_at=date(2026, 12, 1),
        score=0.1,
    )
    assert c.eligibility == "unchecked" and c.reranked is False
    assert c.why == "" and c.matched_chunks == []


def test_preference_kinds_are_closed():
    assert Preference(kind="exclude_agency", value="defense").value == "defense"
    try:
        Preference(kind="favourite_colour", value="x")  # type: ignore[arg-type]
    except ValueError:
        return
    raise AssertionError("unknown preference kind accepted")
