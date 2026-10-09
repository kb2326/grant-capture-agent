from types import SimpleNamespace

from app.config import Settings
from rag.embed import GeminiEmbedder, LocalEmbedder


class FakeModels:
    def __init__(self):
        self.calls = []

    def embed_content(self, model, contents, config):
        self.calls.append(
            (model, list(contents), config.task_type, config.output_dimensionality)
        )
        return SimpleNamespace(
            embeddings=[
                SimpleNamespace(
                    values=[float(i)] * 768, statistics=SimpleNamespace(token_count=5)
                )
                for i, _ in enumerate(contents)
            ]
        )


def test_gemini_embedder_batches_counts_tokens_and_sets_task_types():
    fake = SimpleNamespace(models=FakeModels())
    e = GeminiEmbedder(Settings(_env_file=None), client=fake, batch_size=2)
    vecs = e.embed_documents(["a", "b", "c"])
    assert len(vecs) == 3 and len(vecs[0]) == 768
    assert [c[2] for c in fake.models.calls] == ["RETRIEVAL_DOCUMENT"] * 2
    assert e.tokens == 15
    e.embed_query("q")
    assert fake.models.calls[-1][2:] == ("RETRIEVAL_QUERY", 768)


def test_local_embedder_uses_document_and_query_prompts():
    class FakeST:
        def encode(self, texts, prompt_name, batch_size=32, normalize_embeddings=False):
            assert normalize_embeddings and prompt_name in ("Document", "SearchQuery")
            return [[1.0 if prompt_name == "Document" else 2.0] * 768 for _ in texts]

    e = LocalEmbedder(Settings(_env_file=None), model=FakeST())
    assert e.embed_documents(["a", "b"])[1][0] == 1.0
    assert e.embed_query("q")[0] == 2.0 and e.tokens == 0
