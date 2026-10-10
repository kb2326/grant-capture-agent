import uuid
from pathlib import Path

from app.analyze.quotes import PageText, apply_verification
from app.config import Settings
from app.contracts import (
    DraftSection,
    DraftTask,
    ModelBrief,
    ModelCitation,
    ModelRequirement,
    Paragraph,
    TaskRequirement,
    to_brief,
)

QUOTE = "Applications substantially developed by AI will not be considered."


def test_ai_policy_is_mapped_and_verified():
    doc = uuid.uuid4()
    mb = ModelBrief(
        ai_policy=[
            ModelRequirement(
                text="AI rule", citation=ModelCitation(doc=1, page=1, quote=QUOTE)
            ),
            ModelRequirement(
                text="invented",
                citation=ModelCitation(
                    doc=1, page=1, quote="This sentence is not in the document at all."
                ),
            ),
        ]
    )
    brief = to_brief(
        mb,
        [doc],
        opportunity_id=uuid.uuid4(),
        variant="B0",
        model="m",
        prompt_version="brief_v2",
    )
    assert len(brief.ai_policy) == 2 and brief.ai_policy[0].citation.document_id == doc
    checked = apply_verification(brief, {(doc, 1): PageText(QUOTE, True)})
    assert [p.text for p in checked.ai_policy] == ["AI rule"]
    assert checked.dropped_quotes == 1


def test_brief_v2_prompt_asks_for_ai_policy():
    text = Path("app/analyze/prompts/brief_v2.md").read_text(encoding="utf-8")
    assert "ai_policy" in text and Path("app/analyze/prompts/brief_v1.md").exists()


def test_draft_contracts_and_settings():
    t = DraftTask(
        id="T01",
        section_title="Technical Approach",
        instructions="x",
        requirements=[TaskRequirement(id="R1", text="y")],
    )
    d = DraftSection(
        task_id=t.id,
        variant="B1",
        paragraphs=[Paragraph(text="a", citations=[])],
        gaps=["R1"],
    )
    assert d.retrieval_trace == [] and d.invalid_citations == 0
    assert d.paragraphs[0].supported is None
    s = Settings(_env_file=None)
    assert (s.draft_top_k, s.draft_min_relevant, s.draft_max_rewrites) == (8, 2, 2)
    assert s.draft_eval_budget_usd <= 2.5 and s.draft_variant == "B0"
