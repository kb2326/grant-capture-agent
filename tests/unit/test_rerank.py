from types import SimpleNamespace

from app.config import Settings
from rag.rerank import NoRerank, RerankDoc, VertexRanker

DOCS = [RerankDoc("1", "A", "grid"), RerankDoc("2", "B", "battery")]


class FakeRankClient:
    def __init__(self, fail=False):
        self.fail, self.requests = fail, []

    def rank(self, request):
        self.requests.append(request)
        if self.fail:
            raise RuntimeError("503")
        return SimpleNamespace(
            records=[
                SimpleNamespace(id="2", score=0.9),
                SimpleNamespace(id="1", score=0.2),
            ]
        )


def test_vertex_ranker_returns_ranked_ids_and_counts_calls():
    client = FakeRankClient()
    r = VertexRanker(Settings(_env_file=None), client=client)
    assert r.rerank("q", DOCS) == [("2", 0.9), ("1", 0.2)]
    assert r.calls == 1 and client.requests[0].model == "semantic-ranker-default-004"
    assert client.requests[0].ranking_config.endswith(
        "/rankingConfigs/default_ranking_config"
    )


def test_vertex_ranker_failure_means_not_reranked():
    r = VertexRanker(Settings(_env_file=None), client=FakeRankClient(fail=True))
    assert r.rerank("q", DOCS) is None and r.calls == 1


def test_empty_docs_and_no_rerank():
    r = VertexRanker(Settings(_env_file=None), client=FakeRankClient())
    assert r.rerank("q", []) == [] and r.calls == 0
    assert NoRerank().rerank("q", DOCS) is None
