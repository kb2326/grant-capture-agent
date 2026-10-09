from pathlib import Path

import pytest

from evals.discover_ablation import write_ablation
from evals.discover_label import Grade, Grades, label_query
from evals.discover_queries import DraftQuery, split_queries


def test_split_queries_assigns_ids_slices_and_splits():
    items = [DraftQuery(text=f"s{i}", slice="specific") for i in range(13)] + [
        DraftQuery(text=f"v{i}", slice="vague") for i in range(7)
    ]
    golden, dev = split_queries(items)
    assert len(golden) == 15 and len(dev) == 5
    assert [q["id"] for q in golden][:2] == ["q01", "q02"] and dev[0]["id"] == "d01"
    assert sum(q["slice"] == "vague" for q in golden) == 5
    assert sum(q["slice"] == "vague" for q in dev) == 2
    with pytest.raises(ValueError):
        split_queries(items[:5])


class FakeLLM:
    model_id, total_tokens_in, total_tokens_out = "fake-lite", 0, 0

    def generate(self, schema, instruction, content):
        assert "[0]" in content and "[1]" in content
        return Grades(
            items=[
                Grade(index=0, grade=2, reason="fits"),
                Grade(index=1, grade=7, reason="clamped"),
                Grade(index=9, grade=1, reason="unknown index"),
            ]
        )


def test_label_query_maps_indexes_and_clamps_grades():
    out = label_query(
        FakeLLM(),
        "q01",
        "inverters",
        [("o1", "card one"), ("o2", "card two")],
        {"core_capabilities": []},
    )
    assert out == [
        {"query_id": "q01", "opportunity_id": "o1", "grade": 2, "reason": "fits"},
        {"query_id": "q01", "opportunity_id": "o2", "grade": 2, "reason": "clamped"},
    ]


def test_write_ablation_tables_and_caveats(tmp_path: Path):
    row = {
        "p@10": 0.5,
        "ndcg@10": 0.6,
        "recall@20": 0.5,
        "p50_s": 0.3,
        "p95_s": 0.9,
        "cost_usd": 0.0,
        "n": 10,
    }
    s = {"all": {**row, "recall@20": None, "n": 15}, "specific": row, "vague": row}
    path = write_ablation(
        tmp_path,
        [("Embeddings", {"gemini": s, "local": s})],
        ["Keep gemini."],
        {"labeler": "x"},
    )
    md = path.read_text(encoding="utf-8")
    assert "## Embeddings" in md and "| gemini | all |" in md and "n/a" in md
    assert "silver" in md.lower() and "pool" in md.lower() and "Keep gemini." in md
