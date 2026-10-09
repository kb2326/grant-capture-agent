"""Deterministic eligibility rules E0-E7 (M1 spec §5). The model proposes constraints; code decides."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, ValidationError, model_validator

from app.contracts import Clause, EligibilityVerdict, RuleHit

RULES_VERSION = "2026-10-09.3"
ENTITY_TYPES = {
    "for_profit",
    "small_business",
    "nonprofit",
    "university",
    "government",
    "tribal",
    "individual",
}
SBA_SMALL_BUSINESS_MAX_EMPLOYEES = 500


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class EntityTypeC(_Strict):
    allowed: list[str] | None = None
    excluded: list[str] | None = None

    @model_validator(mode="after")
    def _known(self) -> "EntityTypeC":
        values = (self.allowed or []) + (self.excluded or [])
        if not values or not set(values) <= ENTITY_TYPES:
            raise ValueError("unknown or empty entity types")
        return self


class SizeC(_Strict):
    max_employees: int
    includes_affiliates: bool = True


class OwnershipC(_Strict):
    min_us_ownership_pct: float | None = None
    foreign_owned_allowed: bool | None = None

    @model_validator(mode="after")
    def _some(self) -> "OwnershipC":
        if self.min_us_ownership_pct is None and self.foreign_owned_allowed is None:
            raise ValueError("empty ownership constraint")
        return self


class LocationC(_Strict):
    us_only: bool | None = None
    states: list[str] | None = None

    @model_validator(mode="after")
    def _some(self) -> "LocationC":
        if self.us_only is None and not self.states:
            raise ValueError("empty location constraint")
        return self


class RegistrationC(_Strict):
    requires: list[Literal["sam", "uei"]]


class PhaseC(_Strict):
    requires_prior_phase: Literal["I", "II"]


class CostShareC(_Strict):
    min_pct: float


SCHEMAS: dict[str, type[BaseModel]] = {
    "entity_type": EntityTypeC,
    "size": SizeC,
    "ownership": OwnershipC,
    "location": LocationC,
    "registration": RegistrationC,
    "program_phase": PhaseC,
    "cost_share": CostShareC,
}


class CompanyFacts(BaseModel):
    entity_type: str
    employees: int
    us_ownership_pct: float
    foreign_affiliation: bool
    state: str
    sam_registered: bool
    uei: str | None = None
    sbir_awards: dict[str, int]

    @classmethod
    def from_profile(cls, profile: dict) -> "CompanyFacts":
        return cls(**{k: profile[k] for k in cls.model_fields if k in profile})

    def entity_types(self) -> set[str]:
        types = {self.entity_type}
        if (
            self.entity_type == "for_profit"
            and self.employees <= SBA_SMALL_BUSINESS_MAX_EMPLOYEES
        ):
            types.add("small_business")
        return types


def validate_constraint(category: str, constraint: dict | None) -> BaseModel | None:
    schema = SCHEMAS.get(category)
    if schema is None or constraint is None:
        return None
    try:
        return schema.model_validate(constraint)
    except ValidationError:
        return None


def _hit(rule: str, outcome: str, clause: Clause, fact: str, reason: str) -> RuleHit:
    return RuleHit(
        rule_id=rule, outcome=outcome, clause=clause, company_fact=fact, reason=reason
    )


def evaluate_clause(clause: Clause, f: CompanyFacts) -> RuleHit | None:
    if clause.category == "other":
        return None
    c = validate_constraint(clause.category, clause.constraint)
    if c is None:
        return _hit(
            "E0",
            "NEEDS_REVIEW",
            clause,
            "-",
            "clause could not be turned into a checkable constraint",
        )
    if isinstance(c, EntityTypeC):
        types = f.entity_types()
        if c.allowed and not types & set(c.allowed):
            return _hit(
                "E1",
                "INELIGIBLE",
                clause,
                f"entity_types={sorted(types)}",
                f"allowed only {c.allowed}",
            )
        if c.excluded and types & set(c.excluded):
            return _hit(
                "E1",
                "INELIGIBLE",
                clause,
                f"entity_types={sorted(types)}",
                f"excluded {c.excluded}",
            )
        return _hit(
            "E1",
            "PASS",
            clause,
            f"entity_types={sorted(types)}",
            "entity type permitted",
        )
    if isinstance(c, SizeC):
        ok = f.employees <= c.max_employees
        return _hit(
            "E2",
            "PASS" if ok else "INELIGIBLE",
            clause,
            f"employees={f.employees}",
            f"limit {c.max_employees}",
        )
    if isinstance(c, OwnershipC):
        if (
            c.min_us_ownership_pct is not None
            and f.us_ownership_pct < c.min_us_ownership_pct
        ):
            return _hit(
                "E3",
                "INELIGIBLE",
                clause,
                f"us_ownership_pct={f.us_ownership_pct}",
                f"minimum {c.min_us_ownership_pct}",
            )
        if c.foreign_owned_allowed is False and f.foreign_affiliation:
            return _hit(
                "E3",
                "INELIGIBLE",
                clause,
                "foreign_affiliation=True",
                "foreign ownership not allowed",
            )
        return _hit(
            "E3",
            "PASS",
            clause,
            f"us_ownership_pct={f.us_ownership_pct}",
            "ownership permitted",
        )
    if isinstance(c, LocationC):
        if c.states and f.state not in c.states:
            return _hit(
                "E4", "INELIGIBLE", clause, f"state={f.state}", f"only {c.states}"
            )
        return _hit("E4", "PASS", clause, f"state={f.state}", "location permitted")
    if isinstance(c, RegistrationC):
        missing = [
            r
            for r in c.requires
            if (r == "sam" and not f.sam_registered) or (r == "uei" and not f.uei)
        ]
        return _hit(
            "E5",
            "INELIGIBLE" if missing else "PASS",
            clause,
            f"sam_registered={f.sam_registered}",
            f"missing {missing}" if missing else "registered",
        )
    if isinstance(c, PhaseC):
        held = f.sbir_awards.get(c.requires_prior_phase, 0)
        return _hit(
            "E6",
            "PASS" if held else "INELIGIBLE",
            clause,
            f"sbir_awards={f.sbir_awards}",
            f"requires prior Phase {c.requires_prior_phase}",
        )
    return _hit("E7", "NEEDS_REVIEW", clause, "-", "cost share is a business decision")


def _list_unions(clauses: list[Clause]) -> dict[int, set[str]]:
    """Group entity-type clauses into lists: same document, pages consecutive (a list may cross a page break).

    Solicitations list eligible applicant types as bullets, one clause each; within one list they mean ANY
    of them. Lists in other sections or documents (e.g. "small businesses may be subawardees") stay separate,
    so they can't rescue a real knockout. Returns clause index -> union of its list's allowed types.
    """
    typed = []
    for i, c in enumerate(clauses):
        parsed = (
            validate_constraint(c.category, c.constraint)
            if c.category == "entity_type"
            else None
        )
        if isinstance(parsed, EntityTypeC):
            typed.append(
                (
                    str(c.citation.document_id),
                    c.citation.page,
                    i,
                    set(parsed.allowed or []),
                )
            )
    unions: dict[int, set[str]] = {}
    group: list[tuple] = []
    for item in sorted(typed, key=lambda t: (t[0], t[1])):
        if group and (item[0] != group[-1][0] or item[1] - group[-1][1] > 1):
            union = set().union(*(g[3] for g in group))
            unions.update({g[2]: union for g in group})
            group = []
        group.append(item)
    if group:
        union = set().union(*(g[3] for g in group))
        unions.update({g[2]: union for g in group})
    return unions


def decide(clauses: list[Clause], facts: CompanyFacts) -> EligibilityVerdict:
    unions = _list_unions(clauses)
    hits = []
    for i, original in enumerate(clauses):
        c = original
        if unions.get(i):
            # judge each listed type against its whole list, keeping this clause's own exclusions
            c = c.model_copy(
                update={"constraint": {**c.constraint, "allowed": sorted(unions[i])}}
            )
        hit = evaluate_clause(c, facts)
        if hit is not None:
            hits.append(hit.model_copy(update={"clause": original}))
    outcomes = {h.outcome for h in hits}
    status = (
        "INELIGIBLE"
        if "INELIGIBLE" in outcomes
        else "NEEDS_REVIEW"
        if "NEEDS_REVIEW" in outcomes
        else "ELIGIBLE"
    )
    return EligibilityVerdict(status=status, hits=hits, rules_version=RULES_VERSION)
