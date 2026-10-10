import uuid

from app.contracts import DraftTask, TaskRequirement
from app.draft.corpus import label_chunks, render_chunks
from app.draft.generate import (
    DRAFT_RULES,
    ModelDraft,
    ModelParagraph,
    generate_section,
    validate,
)

ROWS = [
    (
        uuid.uuid4(),
        "capability-statement-2025-update.md",
        "Overview",
        "We have 32 employees.",
    ),
    (uuid.uuid4(), "capability-statement-2021.md", "Overview", "We have 18 employees."),
]
CHUNKS = label_chunks(ROWS)
TASK = DraftTask(
    id="T10",
    section_title="Company Overview",
    instructions="x",
    requirements=[
        TaskRequirement(id="R1", text="headcount"),
        TaskRequirement(id="R4", text="hydrogen"),
    ],
)


class FakeLLM:
    model_id, total_tokens_in, total_tokens_out = "fake", 0, 0

    def __init__(self, *outs):
        self.outs, self.contents = list(outs), []

    def generate(self, schema, instruction, content, **kw):
        self.contents.append(content)
        return self.outs.pop(0)


def test_labels_and_render_include_titles():
    assert [c.label for c in CHUNKS] == ["C1", "C2"]
    text = render_chunks(CHUNKS)
    assert (
        "[C1] capability-statement-2025-update.md > Overview" in text
        and "18 employees" in text
    )


def test_validate_maps_labels_and_reports_unknown_ones():
    labels = {c.label: c for c in CHUNKS}
    draft = ModelDraft(
        paragraphs=[ModelParagraph(text="32 staff.", citations=["C1", "C9", "c1"])],
        gaps=["R4", "R7"],
    )
    paras, gaps, errors = validate(draft, labels, {"R1", "R4"})
    assert paras[0].citations == [ROWS[0][0]] and gaps == ["R4"]
    assert any("C9" in e for e in errors) and any("R7" in e for e in errors)


def test_generate_retries_once_then_strips_invented_labels():
    bad = ModelDraft(
        paragraphs=[ModelParagraph(text="32 staff.", citations=["C9"])], gaps=[]
    )
    llm = FakeLLM(bad, bad)
    paras, _gaps, invalid = generate_section(llm, TASK, CHUNKS)
    assert (
        len(llm.contents) == 2
        and "C9" in llm.contents[1]
        and paras[0].citations == []
        and invalid == 1
    )


def test_forced_gaps_are_kept_and_rules_prefer_newer_docs():
    ok = ModelDraft(
        paragraphs=[ModelParagraph(text="32 staff.", citations=["C1"])], gaps=[]
    )
    _paras, gaps, invalid = generate_section(
        FakeLLM(ok), TASK, CHUNKS, forced_gaps=["R4"]
    )
    assert gaps == ["R4"] and invalid == 0
    assert "newer" in DRAFT_RULES.lower() and "gaps" in DRAFT_RULES
