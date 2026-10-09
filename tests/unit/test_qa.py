import uuid

from app.analyze.extract import LoadedDoc
from app.analyze.qa import answer_question
from app.analyze.quotes import PageText
from app.config import Settings

DOC = LoadedDoc(
    id=uuid.uuid4(),
    title="n.html",
    kind="html",
    data=b"",
    pages=[
        (
            1,
            PageText(
                "The full application is due November 3, 2026 at 5 PM Eastern.", True
            ),
        )
    ],
)


class _Resp:
    text = '{"answer": "November 3, 2026", "citations": [{"doc": 1, "page": 1, "quote": "due November 3, 2026"}]}'


class FakeModels:
    def __init__(self) -> None:
        self.configs = []

    def generate_content(self, model, contents, config):
        self.configs.append(config)
        return _Resp()


class FailingCaches:
    def create(self, **kwargs):
        raise RuntimeError("Cached content is too small")


class FakeClient:
    def __init__(self) -> None:
        self.models, self.caches = FakeModels(), FailingCaches()


def test_qa_falls_back_without_cache_and_verifies_citations():
    client = FakeClient()
    out = answer_question(
        [DOC], "When is it due?", client, Settings(_env_file=None), cache_store={}
    )
    assert out["answer"] == "November 3, 2026"
    assert out["citations"][0]["page"] == 1 and out["unverified"] == 0
    assert client.models.configs[0].cached_content is None


class ExpiringModels(FakeModels):
    def generate_content(self, model, contents, config):
        self.configs.append(config)
        if config.cached_content:
            raise RuntimeError("404 CachedContent not found (expired)")
        return _Resp()


def test_expired_cache_is_dropped_and_the_question_answered_uncached():
    client = FakeClient()
    client.models = ExpiringModels()
    store = {str(DOC.id): "cachedContents/old"}
    out = answer_question(
        [DOC], "When is it due?", client, Settings(_env_file=None), cache_store=store
    )
    assert out["answer"] == "November 3, 2026" and store == {}
    assert client.models.configs[-1].cached_content is None
