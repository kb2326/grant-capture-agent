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


def test_warm_up_touches_embedder_ranker_and_llm_once():
    from types import SimpleNamespace

    from evals.discover import warm_up

    calls = []
    deps = SimpleNamespace(
        embedder=SimpleNamespace(embed_query=lambda t: calls.append("embed")),
        reranker=SimpleNamespace(rerank=lambda q, docs: calls.append("rerank")),
        llm=SimpleNamespace(
            client=SimpleNamespace(
                models=SimpleNamespace(
                    count_tokens=lambda model, contents: calls.append("llm")
                )
            ),
            model_id="m",
        ),
    )
    warm_up(deps)
    assert calls == ["embed", "rerank", "llm"]
    warm_up(SimpleNamespace(embedder=deps.embedder, reranker=deps.reranker, llm=None))
    assert calls[-2:] == ["embed", "rerank"]


def test_workflow_verdict_is_inconclusive_when_the_loop_never_ran():
    from evals.discover import workflow_verdict

    s = {"all": {"ndcg@10": 0.46}, "vague": {"ndcg@10": 0.60}}
    t = {"all": {"ndcg@10": 0.42}, "vague": {"ndcg@10": 0.54}}
    text = workflow_verdict(s, t, refined=0, n=15)
    assert "inconclusive" in text and "0 of 15" in text
    assert "inconclusive" not in workflow_verdict(s, t, refined=4, n=15)
