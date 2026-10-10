from pathlib import Path

from ingest.company_corpus import (
    DENY_ON_TOPIC,
    GAP_TERMS,
    check_corpus,
    check_doc,
    check_tasks,
    kinds,
    load_plan,
    load_tasks,
)

PLAN = load_plan(Path("data/company/corpus_plan.json"))
DOCS = Path("data/company/docs")
BANNER = "> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional."


def test_plan_shape():
    k = kinds(PLAN)
    assert len(k) == 75 and len(PLAN["new"]) == 62
    assert (
        sum(v == "outdated" for v in k.values()) == 15
        and sum(v == "off_topic" for v in k.values()) == 12
    )


def test_check_doc_finds_each_problem():
    entry = {"file": "x.md", "kind": "on_topic", "phrases": ["UL 1741 SB"]}
    assert check_doc(f"{BANNER}\n# X\nPassed UL 1741 SB.", entry) == []
    probs = check_doc("# X\nWe have 18 employees and a hydrogen line.", entry)
    assert any("banner" in p for p in probs) and any("UL 1741 SB" in p for p in probs)
    assert any("18 employees" in p for p in probs) and any(
        "hydrogen" in p for p in probs
    )
    outdated = {"file": "y.md", "kind": "outdated", "phrases": ["18 employees"]}
    assert check_doc(f"{BANNER}\nIn 2021 we had 18 employees.", outdated) == []


def test_checked_in_docs_pass():
    assert (
        check_corpus(DOCS, PLAN) == []
    )  # missing generated files are skipped until Task 15


def test_tasks_are_consistent_with_the_plan():
    tasks = load_tasks(Path("evals/data/golden/draft_tasks.jsonl"))
    assert len(tasks) == 12 and sum(len(t["requirements"]) for t in tasks) == 46
    assert sum("gap_terms" in r for t in tasks for r in t["requirements"]) == 10
    assert check_tasks(tasks, PLAN, DOCS) == []
    assert "hydrogen" in GAP_TERMS and "18 employees" in DENY_ON_TOPIC


from ingest.company_corpus import BANNER as REAL_BANNER  # noqa: E402
from ingest.company_corpus import DocText, generate_missing  # noqa: E402


class FakeLLM:
    model_id, total_tokens_in, total_tokens_out = "fake", 0, 0

    def __init__(self, *texts):
        self.texts, self.calls = list(texts), 0

    def generate(self, schema, instruction, content):
        self.calls += 1
        self.total_tokens_in += 1000
        self.total_tokens_out += 1000
        return DocText(markdown=self.texts.pop(0))


def test_generate_writes_missing_retries_once_and_never_overwrites(tmp_path):
    plan = {
        "originals": [],
        "new": [
            {
                "file": "a.md",
                "kind": "on_topic",
                "title": "A",
                "brief": "b",
                "phrases": ["UL 1741 SB"],
            },
            {
                "file": "b.md",
                "kind": "off_topic",
                "title": "B",
                "brief": "b",
                "phrases": ["per diem"],
            },
            {
                "file": "c.md",
                "kind": "on_topic",
                "title": "C",
                "brief": "b",
                "phrases": ["zero unplanned trips"],
            },
        ],
    }
    (tmp_path / "b.md").write_text("existing", encoding="utf-8")
    llm = FakeLLM(
        f"{REAL_BANNER}\n# A\nno phrase",
        f"{REAL_BANNER}\n# A\nPassed UL 1741 SB.",
        "# C\nmissing banner",
        "# C\nstill missing",
    )
    out = generate_missing(
        plan,
        tmp_path,
        llm,
        "facts",
        price_in_per_m=0.0,
        price_out_per_m=0.0,
        max_usd=1.0,
    )
    assert (
        out["written"] == 1
        and out["skipped"] == 1
        and out["failed"] == 1
        and llm.calls == 4
    )
    assert (tmp_path / "b.md").read_text(encoding="utf-8") == "existing" and not (
        tmp_path / "c.md"
    ).exists()


def test_generate_stops_at_budget(tmp_path):
    plan = {
        "originals": [],
        "new": [
            {
                "file": f"{i}.md",
                "kind": "off_topic",
                "title": "t",
                "brief": "b",
                "phrases": [],
            }
            for i in range(3)
        ],
    }
    llm = FakeLLM(*[f"{REAL_BANNER}\n# t"] * 3)
    out = generate_missing(
        plan,
        tmp_path,
        llm,
        "facts",
        price_in_per_m=1e3,
        price_out_per_m=0.0,
        max_usd=1.5,
    )
    assert out["written"] == 2 and out["stopped"] == "budget"
