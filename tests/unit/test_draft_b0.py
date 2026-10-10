import uuid
from types import SimpleNamespace

from app.config import Settings
from app.contracts import DraftTask, TaskRequirement
from app.discover.llm import GeminiJson
from app.draft.b0_long import CorpusCache, draft_b0
from app.draft.corpus import label_chunks
from app.draft.generate import ModelDraft, ModelParagraph

CHUNKS = label_chunks([(uuid.uuid4(), "a.md", "s", "We have 32 employees.")])
TASK = DraftTask(
    id="T",
    section_title="s",
    instructions="i",
    requirements=[TaskRequirement(id="R1", text="x")],
)
OK = ModelDraft(paragraphs=[ModelParagraph(text="32.", citations=["C1"])], gaps=[])


class FakeCaches:
    def __init__(self, fail=False):
        self.fail, self.created = fail, 0

    def create(self, model, config):
        self.created += 1
        if self.fail:
            raise RuntimeError("too small")
        return SimpleNamespace(name="cachedContents/1")

    def delete(self, name):
        pass


def test_cache_created_once_and_none_on_failure():
    caches = FakeCaches()
    c = CorpusCache(SimpleNamespace(caches=caches), "m", CHUNKS, 1800)
    assert c.name() == c.name() == "cachedContents/1" and caches.created == 1
    assert (
        CorpusCache(
            SimpleNamespace(caches=FakeCaches(fail=True)), "m", CHUNKS, 1800
        ).name()
        is None
    )


class LLM:
    model_id, total_tokens_in, total_tokens_out = "m", 0, 0

    def __init__(self, fail_cached=False):
        self.fail_cached, self.calls = fail_cached, []

    def generate(self, schema, instruction, content, cached_content=None):
        self.calls.append(cached_content)
        if cached_content and self.fail_cached:
            raise RuntimeError("cache expired")
        return OK


def test_b0_uses_cache_and_falls_back_uncached():
    cache = CorpusCache(SimpleNamespace(caches=FakeCaches()), "m", CHUNKS, 1800)
    llm = LLM()
    assert draft_b0(llm, TASK, CHUNKS, cache)[0][0].citations == [
        CHUNKS[0].chunk_id
    ] and llm.calls == ["cachedContents/1"]
    llm = LLM(fail_cached=True)
    paras, _gaps, _invalid = draft_b0(llm, TASK, CHUNKS, cache)
    assert llm.calls == ["cachedContents/1", None] and paras[0].citations == [
        CHUNKS[0].chunk_id
    ]


def test_gemini_json_passes_cached_content_without_system_instruction():
    seen = {}

    class Models:
        def generate_content(self, model, contents, config):
            seen["config"] = config
            return SimpleNamespace(text=OK.model_dump_json(), usage_metadata=None)

    GeminiJson(
        Settings(_env_file=None), client=SimpleNamespace(models=Models())
    ).generate(ModelDraft, "rules", "task", cached_content="cachedContents/1")
    assert (
        seen["config"].cached_content == "cachedContents/1"
        and seen["config"].system_instruction is None
    )


def test_gemini_json_caps_thinking_when_asked():
    seen = {}

    class Models:
        def generate_content(self, model, contents, config):
            seen["config"] = config
            return SimpleNamespace(text=OK.model_dump_json(), usage_metadata=None)

    client = SimpleNamespace(models=Models())
    GeminiJson(Settings(_env_file=None), client=client, thinking_budget=512).generate(
        ModelDraft, "r", "t"
    )
    assert seen["config"].thinking_config.thinking_budget == 512
    GeminiJson(Settings(_env_file=None), client=client).generate(ModelDraft, "r", "t")
    assert seen["config"].thinking_config is None
    assert Settings(_env_file=None).draft_thinking_budget == 1024
