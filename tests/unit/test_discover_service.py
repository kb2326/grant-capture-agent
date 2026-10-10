import uuid
from datetime import date
from types import SimpleNamespace

import pytest

from app.config import Settings
from app.contracts import SearchPlan, SearchQuery
from app.discover import service
from app.discover.service import DiscoverDeps, execute, filters_for, run_plan
from rag.search import Hit

IDS = [uuid.UUID(int=i) for i in range(1, 9)]


def opp(i, **over):
    data = dict(
        id=IDS[i],
        source_id=f"s{i}",
        title=f"T{i}",
        agency="DOE",
        status="open",
        close_at=date(2027, 1, 1),
    )
    data.update(over)
    return SimpleNamespace(**data)


class FakeEmbedder:
    name, tokens = "fake", 0

    def embed_query(self, text):
        self.tokens += 10
        return [0.0] * 768


class FakeRanker:
    name = "fake"

    def __init__(self, result):
        self.result, self.calls = result, 0

    def rerank(self, query, docs):
        self.calls += 1
        return self.result


@pytest.fixture
def patched(monkeypatch):
    rows = {IDS[i]: (opp(i), f"card {i}") for i in range(8)}
    hits_by_query = {
        "a": [Hit(IDS[0], 0.03, 1, 1), Hit(IDS[1], 0.02, 2, None)],
        "b": [Hit(IDS[1], 0.025, 1, None), Hit(IDS[2], 0.01, None, 3)],
        "late": [Hit(IDS[i], 0.01, i, None) for i in range(3, 8)],
    }
    monkeypatch.setattr(
        service,
        "_search",
        lambda session, **kw: hits_by_query.get(kw["query_text"], []),
    )
    monkeypatch.setattr(
        service, "_load", lambda session, ids: {i: rows[i] for i in ids if i in rows}
    )
    return rows


def deps(ranker=None, **over):
    data = dict(
        session=None,
        settings=Settings(_env_file=None),
        embedder=FakeEmbedder(),
        column="emb_local",
        reranker=ranker or FakeRanker(None),
        today=date(2026, 10, 9),
    )
    data.update(over)
    return DiscoverDeps(**data)


def plan(*texts):
    return SearchPlan(
        intent="grid",
        queries=[SearchQuery(text=t, min_days_to_close=0) for t in texts],
    )


def test_execute_merges_queries_by_best_score_in_fused_order(patched):
    cands = execute(deps(), plan("a", "b"))
    assert [c.opportunity_id for c in cands] == [IDS[0], IDS[1], IDS[2]]
    assert cands[1].score == 0.025 and not any(c.reranked for c in cands)


def test_rerank_order_wins_and_missing_records_follow_in_fused_order(patched):
    ranker = FakeRanker([(str(IDS[2]), 0.9)])  # the ranker returned only one of three
    cands = execute(deps(ranker), plan("a", "b"))
    assert [c.opportunity_id for c in cands] == [IDS[2], IDS[0], IDS[1]]
    assert cands[0].reranked and cands[0].score == 0.9 and not cands[1].reranked


def test_filters_for_combines_query_and_plan():
    q = SearchQuery(text="x", kinds=["sbir"], min_days_to_close=10, award_min=5.0)
    f = filters_for(
        q, SearchPlan(intent="i", queries=[q], exclude=["defense"]), date(2026, 10, 1)
    )
    assert (f.kinds, f.min_close, f.award_min, f.exclude_agencies) == (
        ["sbir"],
        date(2026, 10, 11),
        5.0,
        ["defense"],
    )


class PlanLLM:
    model_id, total_tokens_in, total_tokens_out = "fake", 0, 0

    def __init__(self, *plans):
        self.plans = list(plans)

    def generate(self, schema, instruction, content):
        self.total_tokens_in += 100
        self.total_tokens_out += 10
        return self.plans.pop(0)


def _run(d, variant, first=("a",)):
    return run_plan(
        d,
        "req",
        plan(*first),
        variant=variant,
        profile={},
        prefs=[],
        explain_top=False,
    )


def test_b0_runs_once_b1_refines_until_k(patched):
    r0 = _run(deps(llm=PlanLLM(plan("late"))), "B0")
    assert r0.iterations == 1 and len(r0.candidates) == 2
    r1 = _run(deps(llm=PlanLLM(plan("late"))), "B1")
    assert r1.iterations == 2 and len(r1.candidates) == 7
    # first-pass results stay first
    assert [c.opportunity_id for c in r1.candidates[:2]] == [IDS[0], IDS[1]]


def test_b1_stops_on_repeated_plan_and_at_iteration_cap(patched):
    r = _run(deps(llm=PlanLLM(plan("a"))), "B1")
    assert r.iterations == 1 and len(r.plans) == 1
    llm = PlanLLM(plan("b"), plan("zzz"), plan("never"))
    r = _run(deps(llm=llm), "B1")
    assert r.iterations == 3 and len(llm.plans) == 1


def test_cost_counts_llm_embeddings_and_rerank_calls(patched):
    s = Settings(_env_file=None)
    d = deps(FakeRanker(None), llm=PlanLLM(), embedder=FakeEmbedder())
    d.embedder.name = "gemini"
    r = _run(d, "B0", first=("a", "b"))
    expected = 20 * s.price_embedding_per_m / 1e6 + 1 * s.price_rank_per_1k / 1000
    assert r.cost_usd == pytest.approx(expected)


def test_discover_cost_includes_the_planning_call(patched):
    from app.discover.service import discover

    s = Settings(_env_file=None)
    d = deps(llm=PlanLLM(plan("a")))
    r = discover(d, "req", variant="B0", profile={}, prefs=[], explain_top=False)
    assert (r.tokens_in, r.tokens_out) == (100, 10)
    expected = (
        100 * s.price_agent_input_per_m / 1e6 + 10 * s.price_agent_output_per_m / 1e6
    )
    assert r.cost_usd == pytest.approx(expected + 1 * s.price_rank_per_1k / 1000)
