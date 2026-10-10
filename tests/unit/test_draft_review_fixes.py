"""Final-review findings I1, I3, I4, I5 (M3): pinned by tests before the fixes."""

import uuid
from types import SimpleNamespace

from app.config import Settings
from app.contracts import Citation, Requirement, SolicitationBrief


# I1: citations the model invented (removed by validation) must lower citation validity
def test_citation_validity_counts_removed_labels():
    from evals.suites.draft import score_section, summarize_draft

    task = {"id": "T", "requirements": [{"id": "R1", "evidence": ["x"]}]}
    section = {
        "gaps": [],
        "paragraphs": [{"citations": ["a"]}],
        "invalid_citations": 3,
        "given": [],
    }
    row = score_section(task, section, {"a": "x"}, {"a": "on_topic"})
    assert summarize_draft([row])["citation_validity"] == 0.25


# I3: spend is seeded from saved rows (resume) and counts failed calls via token counters
def test_eval_spend_seeds_from_saved_rows_and_counts_tokens():
    from evals.draft import seed_spent, tokens_cost

    rows = [
        {"stats": {"cost_usd": 0.2}},
        {"stats": {"cost_usd": 0.3}},
        {"error": "x", "stats": {"latency_s": 1}},
    ]
    assert seed_spent(rows) == 0.5
    s = Settings(_env_file=None)
    deps = SimpleNamespace(
        llm=SimpleNamespace(total_tokens_in=1_000_000, total_tokens_out=0),
        grader=SimpleNamespace(total_tokens_in=0, total_tokens_out=1_000_000),
    )
    assert (
        tokens_cost(deps, s) == s.price_agent_input_per_m + s.price_grader_output_per_m
    )


# I4: a brief analyzed before brief_v2 never checked AI-use rules; say so instead of showing nothing
def test_old_briefs_warn_that_ai_rules_were_not_checked():
    from app.draft.tools import ai_warnings

    old = SolicitationBrief(
        opportunity_id=uuid.uuid4(), variant="B0", model="m", prompt_version="brief_v1"
    )
    assert len(ai_warnings(old)) == 1 and "not checked" in ai_warnings(old)[0]
    new = old.model_copy(update={"prompt_version": "brief_v2"})
    assert ai_warnings(new) == []
    doc = uuid.uuid4()
    rule = Requirement(
        text="No AI", citation=Citation(document_id=doc, page=2, quote="q")
    )
    assert ai_warnings(new.model_copy(update={"ai_policy": [rule]})) == [
        'No AI ("q", p. 2)'
    ]


# I5: the paid context cache is always deleted after tool/workflow drafting, even on errors
def test_draft_with_cleanup_deletes_cache_even_on_error():
    from app.draft.tools import draft_with_cleanup

    deleted = []
    deps = SimpleNamespace(cache=SimpleNamespace(delete=lambda: deleted.append(1)))
    assert draft_with_cleanup(deps, lambda d: "ok") == "ok" and deleted == [1]
    try:
        draft_with_cleanup(deps, lambda d: (_ for _ in ()).throw(RuntimeError("boom")))
    except RuntimeError:
        pass
    assert deleted == [1, 1]
