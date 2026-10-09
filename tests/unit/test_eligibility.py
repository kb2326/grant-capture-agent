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


def clause(category: str, constraint: dict | None) -> Clause:
    return Clause(
        category=category,
        constraint=constraint,
        citation=Citation(document_id=uuid.uuid4(), page=1, quote="quoted clause text"),
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
