"""Final-review findings I1-I4 (M2): pinned by tests before the fixes."""

import uuid
from datetime import date

from app.config import Settings
from app.contracts import SearchPlan, SearchQuery
from app.discover import service
from app.discover.service import DiscoverDeps, discover, filters_for, run_plan
from rag.search import Hit

IDS = [uuid.UUID(int=i) for i in range(1, 9)]


class _Opp:
    def __init__(self, i):
        self.id, self.source_id, self.title = IDS[i], f"s{i}", f"T{i}"
        self.agency, self.status, self.close_at = "DOE", "open", date(2027, 1, 1)


class _Emb:
    name, tokens = "fake", 0

    def embed_query(self, text):
        return [0.0] * 768


class _NoRank:
    name, calls = "none", 0

    def rerank(self, q, docs):
        return None


class _Checker:
    def __init__(self):
        self.calls, self.cost_usd = 0, 0.0

    def check(self, opportunity_id):
        self.calls += 1
        self.cost_usd += 0.04
        return "ELIGIBLE"


class _PlanLLM:
    model_id, total_tokens_in, total_tokens_out = "fake", 0, 0

    def __init__(self, *plans):
        self.plans = list(plans)

    def generate(self, schema, instruction, content):
        return self.plans.pop(0)


def _patch(monkeypatch, hits_by_query):
    rows = {IDS[i]: (_Opp(i), f"card {i}") for i in range(8)}
    monkeypatch.setattr(
        service,
        "_search",
        lambda session, **kw: hits_by_query.get(kw["query_text"], []),
    )
    monkeypatch.setattr(
        service, "_load", lambda session, ids: {i: rows[i] for i in ids if i in rows}
    )


def _deps(**over):
    data = dict(
        session=None,
        settings=Settings(_env_file=None),
        embedder=_Emb(),
        column="emb_local",
        reranker=_NoRank(),
        today=date(2026, 10, 9),
    )
    data.update(over)
    return DiscoverDeps(**data)


def _plan(*texts, **over):
    return SearchPlan(
        intent="x",
        queries=[SearchQuery(text=t, min_days_to_close=0) for t in texts],
        **over,
    )


# I1: loose agency names map to words that appear in the data
def test_agency_aliases_reach_the_search_filters():
    f = filters_for(
        SearchQuery(text="x"), _plan("x", exclude=["DoD", "HHS"]), date(2026, 1, 1)
    )
    assert f.exclude_agencies == ["defense", "health and human services"]


# I2: blank exclusions never reach SQL (they would match every agency)
def test_blank_exclusions_are_dropped():
    f = filters_for(
        SearchQuery(text="x"),
        _plan("x", exclude=["", "  ", "energy"]),
        date(2026, 1, 1),
    )
    assert f.exclude_agencies == ["energy"]


# I3: an approved/edited plan is repaired before it runs
def test_edited_plan_with_no_queries_is_repaired(monkeypatch):
    _patch(monkeypatch, {"req": [Hit(IDS[0], 0.03, 1, 1)]})
    d = _deps(llm=_PlanLLM(_plan("a")))
    r = discover(
        d,
        "req",
        variant="B0",
        profile={},
        prefs=[],
        explain_top=False,
        approve=lambda p: SearchPlan(intent="", queries=[]),
    )
    assert [q.text for q in r.plan.queries] == ["req"] and len(r.candidates) == 1


def test_run_plan_survives_an_empty_plan(monkeypatch):
    _patch(monkeypatch, {})
    r = run_plan(
        _deps(),
        "req",
        SearchPlan(intent="x", queries=[]),
        variant="B0",
        profile={},
        prefs=[],
        explain_top=False,
    )
    assert r.iterations == 1 and r.candidates == []


# I4: V4 checks are capped per run (not per iteration) and their cost is counted
def test_v4_checks_capped_per_run_and_counted_in_cost(monkeypatch):
    hits = {f"q{i}": [Hit(IDS[i], 0.01, 1, None)] for i in range(8)}
    _patch(monkeypatch, hits)
    checker = _Checker()
    llm = _PlanLLM(_plan("q3", "q4"), _plan("q5", "q6", "q7"))
    d = _deps(llm=llm, checker=checker, company_id=uuid.uuid4())
    r = run_plan(
        d,
        "req",
        _plan("q0", "q1", "q2"),
        variant="B1",
        profile={},
        prefs=[],
        explain_top=False,
    )
    assert checker.calls == Settings(_env_file=None).discover_v4_max_checks == 5
    assert r.cost_usd >= 5 * 0.04
