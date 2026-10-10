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
