import pytest

from evals.suites.discover import (
    keep_richer,
    percentile,
    pool_missing,
    query_metrics,
    recall_at_k,
    run_arm,
    summarize,
    tune_tau,
)


def test_query_metrics_hand_computed():
    grades = {"a": 2, "b": 1, "c": 0, "d": 2}
    m = query_metrics(["a", "c", "b"], grades)
    assert m["p@10"] == pytest.approx(2 / 10)
    # of the label-2 items a and d, only a was found
    assert m["recall@20"] == pytest.approx(1 / 2)
    ideal = 3 + 3 / 1.5849625 + 1 / 2.0
    assert m["ndcg@10"] == pytest.approx((3 + 0 + 1 / 2.0) / ideal)


def test_recall_none_without_relevant_and_percentile():
    assert recall_at_k(["a"], set(), 20) is None
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.5) == 2.0
    assert percentile([], 0.5) is None
    assert percentile([1.0, 2.0, 3.0, 4.0], 0.95) == 4.0


def test_summarize_by_slice_skips_errors():
    queries = {
        "q1": {"slice": "specific"},
        "q2": {"slice": "vague"},
        "q3": {"slice": "vague"},
    }
    runs = [
        {"query_id": "q1", "ranked": ["a"], "latency_s": 1.0, "cost_usd": 0.01},
        {"query_id": "q2", "ranked": ["x"], "latency_s": 3.0, "cost_usd": 0.03},
        {"query_id": "q3", "error": "boom"},
    ]
    qrels = {"q1": {"a": 2}, "q2": {"x": 0, "y": 2}}
    s = summarize(runs, qrels, queries)
    assert s["all"]["n"] == 2 and s["vague"]["n"] == 1 and s["all"]["errors"] == 1
    assert s["specific"]["ndcg@10"] == 1.0 and s["vague"]["ndcg@10"] == 0.0
    assert s["all"]["cost_usd"] == pytest.approx(0.02)


def _s(ndcg, cost, p95, vague=None):
    return {
        "all": {"ndcg@10": ndcg, "cost_usd": cost, "p95_s": p95},
        "vague": {
            "ndcg@10": ndcg if vague is None else vague,
            "cost_usd": cost,
            "p95_s": p95,
        },
    }


def test_keep_richer_rules():
    # a cheap absolute increase is fine even over a free baseline
    assert keep_richer(_s(0.50, 0.0, 0.3), _s(0.55, 0.001, 0.9))
    # gain too small
    assert not keep_richer(_s(0.50, 0.01, 1.0), _s(0.52, 0.01, 1.0))
    # wins on the vague slice
    assert keep_richer(_s(0.50, 0.01, 1.0), _s(0.51, 0.01, 1.0, vague=0.60))
    # cost more than doubles (+$0.04)
    assert not keep_richer(_s(0.50, 0.01, 1.0), _s(0.70, 0.05, 1.0))
    # p95 more than doubles (+7 s)
    assert not keep_richer(_s(0.50, 0.01, 2.0), _s(0.70, 0.01, 9.0))


def test_tune_tau_keeps_90_percent_of_relevant():
    pairs = [
        (0.9, 2),
        (0.8, 1),
        (0.7, 0),
        (0.6, 1),
        (0.5, 1),
        (0.4, 1),
        (0.3, 1),
        (0.2, 1),
        (0.1, 1),
        (0.05, 1),
        (0.01, 1),
    ]
    assert tune_tau(pairs) == 0.05  # 10 relevant; the 9th highest relevant score
    assert tune_tau([(0.5, 0)]) is None


def test_pool_missing_lists_unlabeled_top_items_once():
    runs = {
        "x": [{"query_id": "q1", "ranked": ["a", "b", "c"]}],
        "y": [
            {"query_id": "q1", "ranked": ["c", "d"]},
            {"query_id": "q2", "error": "e"},
        ],
    }
    assert pool_missing(runs, {"q1": {"a": 2}}, depth=2) == {"q1": ["b", "c", "d"]}


def test_run_arm_stops_at_budget_and_records_errors():
    def one(q):
        if q["id"] == "q2":
            raise RuntimeError("x")
        return {"ranked": ["a"], "cost_usd": 0.4}

    out = run_arm([{"id": f"q{i}"} for i in range(1, 5)], one, max_usd=1.0)
    assert [o.get("error", "")[:7] for o in out] == ["", "Runtime", "", "skipped"]
    assert all("latency_s" in o for o in out[:3])
