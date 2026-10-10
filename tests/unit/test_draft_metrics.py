import pytest

from evals.suites.draft import keep_b1, score_section, summarize_draft

TASK = {
    "id": "T",
    "requirements": [
        {"id": "R1", "evidence": ["32 employees"]},
        {"id": "R2", "evidence": ["OPAL-RT"]},
        {"id": "R3", "gap_terms": ["hydrogen"]},
    ],
}
CHUNK_TEXT = {
    "a": "We have 32 employees.",
    "b": "In 2021 we had 18 employees.",
    "c": "OPAL-RT rig",
}
KIND = {"a": "on_topic", "b": "outdated", "c": "on_topic"}


def test_score_section_counts_gaps_evidence_and_distractors():
    section = {
        "gaps": ["R3", "R2"],
        "paragraphs": [
            {"citations": ["a", "b"], "supported": True},
            {"citations": ["zz"], "supported": False},
        ],
        "retrieval_trace": [],
        "given": ["a", "b", "c"],
    }
    s = score_section(TASK, section, CHUNK_TEXT, KIND)
    assert (s["gold_gaps"], s["flagged"], s["true_gaps"]) == (1, 2, 1)
    assert (s["covered"], s["supported_reqs"]) == (
        1,
        2,
    )  # R1 via chunk a; R2 wrongly flagged, not covered
    assert (s["citations"], s["valid_citations"], s["distractor_citations"]) == (
        3,
        2,
        1,
    )
    assert (s["given"], s["cited_given"]) == (3, 2)


def test_summary_and_decision_rule():
    rows = [
        {
            "gold_gaps": 1,
            "flagged": 2,
            "true_gaps": 1,
            "covered": 1,
            "supported_reqs": 2,
            "citations": 3,
            "valid_citations": 2,
            "distractor_citations": 1,
            "given": 3,
            "cited_given": 2,
            "claims": 4,
            "supported": 3,
            "latency_s": 2.0,
            "cost_usd": 0.01,
        }
    ]
    s = summarize_draft(rows)
    assert (
        s["gap_recall"] == 1.0
        and s["gap_precision"] == 0.5
        and s["evidence_recall"] == 0.5
    )
    assert s["faithfulness"] == pytest.approx(0.75) and s[
        "distractor_rate"
    ] == pytest.approx(0.5)
    b0 = {**s, "p95_s": 10.0}
    assert keep_b1(b0, {**b0, "gap_recall": 1.0, "evidence_recall": 0.6}) is True
    assert keep_b1(b0, {**b0, "evidence_recall": 0.53}) is False
    assert keep_b1(b0, {**b0, "faithfulness": 0.9, "cost_usd": 0.05}) is False
