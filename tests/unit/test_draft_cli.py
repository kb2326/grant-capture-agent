from app.config import Settings
from evals.draft import estimate_run_usd, to_task, write_draft_report


def test_to_task_drops_ground_truth_fields():
    t = to_task(
        {
            "id": "T01",
            "section_title": "s",
            "instructions": "i",
            "criteria": ["c"],
            "requirements": [
                {"id": "R1", "text": "x", "evidence": ["e"]},
                {"id": "R2", "text": "y", "gap_terms": ["g"]},
            ],
        }
    )
    assert [r.model_dump() for r in t.requirements] == [
        {"id": "R1", "text": "x"},
        {"id": "R2", "text": "y"},
    ]


def test_estimates_scale_and_b0_is_corpus_bound():
    s = Settings(_env_file=None)
    assert (
        estimate_run_usd("B0", 12, 160_000, s)
        > estimate_run_usd("B0", 12, 80_000, s)
        > 0
    )
    assert (
        estimate_run_usd("B1", 12, 80_000, s)
        == estimate_run_usd("B1", 12, 160_000, s)
        > 0
    )


def test_report_has_caveats(tmp_path):
    row = dict.fromkeys(
        (
            "gap_recall",
            "gap_precision",
            "evidence_recall",
            "citation_validity",
            "distractor_rate",
            "faithfulness",
            "context_precision",
            "p50_s",
            "p95_s",
            "cost_usd",
        ),
        0.5,
    ) | {"n": 12}
    md = write_draft_report(
        tmp_path, {"B0": row, "B1": row}, ["Keep B0."], {"kappa": "0.71"}
    ).read_text(encoding="utf-8")
    assert (
        "| B0 |" in md and "silver" in md.lower() and "Keep B0." in md and "0.71" in md
    )
