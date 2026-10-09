import json
import uuid
from pathlib import Path

from app.contracts import Citation, Clause
from app.rules.eligibility import (
    RULES_VERSION,
    CompanyFacts,
    decide,
    validate_constraint,
)

FACTS = CompanyFacts.from_profile(
    json.loads(Path("data/company/profile.json").read_text(encoding="utf-8"))
)


DOC = uuid.uuid4()


def clause(
    category: str, constraint: dict | None, page: int = 1, doc: uuid.UUID = DOC
) -> Clause:
    return Clause(
        category=category,
        constraint=constraint,
        citation=Citation(document_id=doc, page=page, quote="quoted clause text"),
    )


def status(*clauses: Clause) -> str:
    return decide(list(clauses), FACTS).status


def test_company_profile_facts():
    assert FACTS.employees == 32 and FACTS.entity_types() == {
        "for_profit",
        "small_business",
    }


def test_size_500_or_fewer_including_affiliates_passes():
    assert (
        status(clause("size", {"max_employees": 500, "includes_affiliates": True}))
        == "ELIGIBLE"
    )


def test_nonprofit_or_university_only_is_ineligible():
    assert (
        status(clause("entity_type", {"allowed": ["nonprofit", "university"]}))
        == "INELIGIBLE"
    )


def test_us_based_small_business_passes():
    assert (
        status(
            clause("entity_type", {"allowed": ["small_business"]}),
            clause("location", {"us_only": True}),
        )
        == "ELIGIBLE"
    )


def test_state_restriction():
    assert status(clause("location", {"states": ["AK", "HI"]})) == "INELIGIBLE"
    assert status(clause("location", {"states": ["CO"]})) == "ELIGIBLE"


def test_program_phase():
    assert status(clause("program_phase", {"requires_prior_phase": "I"})) == "ELIGIBLE"
    assert (
        status(clause("program_phase", {"requires_prior_phase": "II"})) == "INELIGIBLE"
    )


def test_ownership_and_registration():
    assert status(clause("ownership", {"min_us_ownership_pct": 51})) == "ELIGIBLE"
    assert status(clause("registration", {"requires": ["sam", "uei"]})) == "ELIGIBLE"


def test_cost_share_is_needs_review_not_knockout():
    assert status(clause("cost_share", {"min_pct": 20})) == "NEEDS_REVIEW"


def test_unparsed_or_invalid_constraint_is_needs_review():
    assert status(clause("entity_type", None)) == "NEEDS_REVIEW"
    assert status(clause("entity_type", {"allowed": ["church"]})) == "NEEDS_REVIEW"
    assert validate_constraint("size", {"max_employees": "many"}) is None


def test_other_category_is_ignored():
    assert status(clause("other", None)) == "ELIGIBLE"


def test_aggregation_ineligible_beats_needs_review():
    v = decide(
        [
            clause("cost_share", {"min_pct": 10}),
            clause("entity_type", {"allowed": ["government"]}),
        ],
        FACTS,
    )
    assert v.status == "INELIGIBLE" and v.rules_version == RULES_VERSION
    assert {h.rule_id for h in v.hits} == {"E7", "E1"}


def test_a_bulleted_list_of_eligible_types_means_any_of_them():
    # "Eligible applicants: higher education; nonprofits; small businesses" -> one clause per bullet
    assert (
        status(
            clause("entity_type", {"allowed": ["university"]}),
            clause("entity_type", {"allowed": ["nonprofit"]}),
            clause("entity_type", {"allowed": ["small_business"]}),
        )
        == "ELIGIBLE"
    )


def test_a_list_without_the_company_type_is_still_a_knockout():
    v = decide(
        [
            clause("entity_type", {"allowed": ["university"]}),
            clause("entity_type", {"allowed": ["nonprofit"]}),
        ],
        FACTS,
    )
    assert v.status == "INELIGIBLE" and [h.outcome for h in v.hits] == [
        "INELIGIBLE",
        "INELIGIBLE",
    ]


def test_exclusions_still_apply_alongside_an_allowed_list():
    assert (
        status(
            clause("entity_type", {"allowed": ["small_business"]}),
            clause("entity_type", {"excluded": ["for_profit"]}),
        )
        == "INELIGIBLE"
    )


def test_hits_report_the_clause_as_extracted():
    v = decide(
        [
            clause("entity_type", {"allowed": ["university"]}),
            clause("entity_type", {"allowed": ["small_business"]}),
        ],
        FACTS,
    )
    assert [h.clause.constraint for h in v.hits] == [
        {"allowed": ["university"]},
        {"allowed": ["small_business"]},
    ]


def test_eligible_types_from_another_section_do_not_rescue_a_knockout():
    # "Eligible applicants: universities; nonprofits" (p3) ... "small businesses may be subawardees" (p9)
    assert (
        status(
            clause("entity_type", {"allowed": ["university"]}, page=3),
            clause("entity_type", {"allowed": ["nonprofit"]}, page=3),
            clause("entity_type", {"allowed": ["small_business"]}, page=9),
        )
        == "INELIGIBLE"
    )


def test_a_list_spanning_a_page_break_is_still_one_list():
    assert (
        status(
            clause("entity_type", {"allowed": ["university"]}, page=3),
            clause("entity_type", {"allowed": ["small_business"]}, page=4),
        )
        == "ELIGIBLE"
    )


def test_lists_in_different_documents_are_not_merged():
    assert (
        status(
            clause("entity_type", {"allowed": ["university"]}, doc=uuid.uuid4()),
            clause("entity_type", {"allowed": ["small_business"]}, doc=uuid.uuid4()),
        )
        == "INELIGIBLE"
    )
