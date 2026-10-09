from app.config import Settings
from evals.discover import decide_retrieval, estimate_workflow_usd, parse_arm


def test_parse_arm():
    assert parse_arm("local+rerank") == ("local", True)
    assert parse_arm("gemini") == ("gemini", False)


def test_workflow_estimate_scales_with_queries():
    s = Settings(_env_file=None)
    assert 0 < estimate_workflow_usd(15, s) < estimate_workflow_usd(30, s)


def _runs(ranked):
    return [{"query_id": "q1", "ranked": ranked, "latency_s": 0.3, "cost_usd": 0.0}]


def test_decide_retrieval_picks_embedding_then_rerank():
    queries = {"q1": {"slice": "vague", "split": "golden"}}
    qrels = {"q1": {"good": 2, "bad": 0}}
    runs = {
        "gemini": _runs(["bad", "good"]),
        "local": _runs(["good", "bad"]),
        "gemini+rerank": _runs(["good"]),
        "local+rerank": _runs(["good", "bad"]),
    }
    emb, rerank, notes = decide_retrieval(runs, qrels, queries)
    assert emb == "local" and rerank is False and len(notes) == 2
