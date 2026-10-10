import uuid

from app.contracts import Citation, Requirement, SectionSpec, SolicitationBrief
from app.draft.tools import ai_warnings, task_from_brief
from app.draft.workflow import parse_draft_approval

DOC = uuid.uuid4()


def cite(page, quote="q"):
    return Citation(document_id=DOC, page=page, quote=quote)


BRIEF = SolicitationBrief(
    opportunity_id=uuid.uuid4(),
    variant="B0",
    model="m",
    prompt_version="brief_v2",
    required_sections=[
        SectionSpec(id="S1", title="Technical Approach", citation=cite(4))
    ],
    requirements=[
        Requirement(text=f"Req {i}", citation=cite(4 if i < 3 else 9))
        for i in range(12)
    ],
    ai_policy=[
        Requirement(
            text="No AI-developed applications",
            citation=cite(2, "substantially developed by AI"),
        )
    ],
)


def test_task_from_brief_prefers_requirements_on_the_section_page_and_caps():
    t = task_from_brief(BRIEF, "Technical Approach")
    assert [r.text for r in t.requirements] == [
        "Req 0",
        "Req 1",
        "Req 2",
    ] and t.requirements[0].id == "R1"
    t = task_from_brief(BRIEF, "Unknown section")
    assert len(t.requirements) == 8 and t.opportunity_id == BRIEF.opportunity_id


def test_ai_warnings_quote_the_page():
    assert ai_warnings(BRIEF) == [
        'No AI-developed applications ("substantially developed by AI", p. 2)'
    ]


def test_draft_approval_parsing_and_workflow_type():
    from google.adk.workflow import Workflow

    from app.draft.workflow import draft_workflow

    assert (
        parse_draft_approval("ok") == "approve"
        and parse_draft_approval(" Yes ") == "approve"
    )
    assert (
        parse_draft_approval("reject") == "reject"
        and parse_draft_approval("no") == "reject"
    )
    assert isinstance(draft_workflow, Workflow)
