import uuid

from app.analyze.quotes import PageText, apply_verification, verify
from app.contracts import Citation, Clause, Requirement, SolicitationBrief

D = uuid.uuid4()
PAGES = {
    (D, 1): PageText(
        "Applicants must have 500 or fewer em- ployees including affiliates.", True
    ),
    (D, 2): PageText("Proposals shall not exceed fifteen", True),
    (D, 3): PageText("pages excluding references and budget.", True),
    (D, 4): PageText("", False),
}


def c(page: int, quote: str) -> Citation:
    return Citation(document_id=D, page=page, quote=quote)


def test_hyphenated_line_break_verifies():
    assert verify(c(1, "500 or fewer employees including affiliates"), PAGES)


def test_quote_spanning_page_break_verifies():
    assert verify(c(2, "shall not exceed fifteen pages excluding references"), PAGES)


def test_wrong_page_and_invented_text_fail():
    assert not verify(c(1, "shall not exceed fifteen pages"), PAGES)
    assert not verify(c(1, "Only nonprofits may apply"), PAGES)


def test_no_text_page_and_short_quote_fail():
    assert not verify(c(4, "anything at all here"), PAGES)
    assert not verify(c(1, "500"), PAGES)


def test_apply_keeps_unverified_clause_as_needs_review_and_drops_other_items():
    brief = SolicitationBrief(
        opportunity_id=uuid.uuid4(),
        variant="B0",
        model="m",
        prompt_version="v",
        eligibility=[
            Clause(
                category="size",
                citation=c(1, "invented clause text here"),
                constraint={"max_employees": 1},
            )
        ],
        requirements=[
            Requirement(text="x", citation=c(1, "invented requirement text"))
        ],
    )
    out = apply_verification(brief, PAGES)
    assert len(out.eligibility) == 1 and out.eligibility[0].constraint is None
    assert out.requirements == [] and out.dropped_quotes == 1


def test_verification_marks_each_clause_so_fidelity_is_not_confused_with_null_constraints():
    brief = SolicitationBrief(
        opportunity_id=uuid.uuid4(),
        variant="B0",
        model="m",
        prompt_version="v",
        eligibility=[
            Clause(
                category="other",
                citation=c(1, "500 or fewer employees including affiliates"),
                constraint=None,
            ),
            Clause(
                category="size",
                citation=c(1, "invented clause text here"),
                constraint={"max_employees": 1},
            ),
        ],
    )
    out = apply_verification(brief, PAGES)
    assert [cl.verified for cl in out.eligibility] == [True, False]
