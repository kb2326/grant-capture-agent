"""Typed hand-offs for the Analyze module (M1 spec §3.2)."""

import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

Category = Literal[
    "entity_type",
    "size",
    "ownership",
    "location",
    "registration",
    "program_phase",
    "cost_share",
    "other",
]


# ---- model-facing schemas (Gemini structured output; documents referenced by position) ----
class ModelCitation(BaseModel):
    doc: int = Field(
        description="1-based position of the document in the input (DOCUMENT k)"
    )
    page: int = Field(
        description="1-based page number (PDF) or section number ([PAGE n] marker)"
    )
    quote: str = Field(
        description="exact text copied from that page; never paraphrased"
    )


class ModelConstraint(BaseModel):
    """Every checkable field, all optional; set only the ones the clause states (rules validate per category)."""

    allowed: list[str] | None = None
    excluded: list[str] | None = None
    max_employees: int | None = None
    includes_affiliates: bool | None = None
    min_us_ownership_pct: float | None = None
    foreign_owned_allowed: bool | None = None
    us_only: bool | None = None
    states: list[str] | None = None
    requires: list[str] | None = None
    requires_prior_phase: str | None = None
    min_pct: float | None = None


class ModelClause(BaseModel):
    category: Category
    citation: ModelCitation
    constraint: ModelConstraint | None = None


class ModelRequirement(BaseModel):
    text: str
    citation: ModelCitation


class ModelCriterion(BaseModel):
    name: str
    weight: str | None = None
    citation: ModelCitation


class ModelSection(BaseModel):
    id: str
    title: str
    page_limit: int | None = None
    citation: ModelCitation


class ModelDeadline(BaseModel):
    label: str
    when: str
    citation: ModelCitation


class ModelBrief(BaseModel):
    eligibility: list[ModelClause] = Field(default_factory=list)
    requirements: list[ModelRequirement] = Field(default_factory=list)
    evaluation_criteria: list[ModelCriterion] = Field(default_factory=list)
    required_sections: list[ModelSection] = Field(default_factory=list)
    deadlines: list[ModelDeadline] = Field(default_factory=list)


# ---- internal contracts ----
class Citation(BaseModel):
    document_id: uuid.UUID
    page: int
    quote: str


class Clause(BaseModel):
    category: Category
    citation: Citation
    constraint: dict | None = None
    verified: bool = (
        True  # set False by quote verification when the quote is not on the cited page
    )


class Requirement(BaseModel):
    text: str
    citation: Citation


class Criterion(BaseModel):
    name: str
    weight: str | None = None
    citation: Citation


class SectionSpec(BaseModel):
    id: str
    title: str
    page_limit: int | None = None
    citation: Citation


class Deadline(BaseModel):
    label: str
    when: str
    citation: Citation


class SolicitationBrief(BaseModel):
    opportunity_id: uuid.UUID
    variant: Literal["B0", "B1"]
    eligibility: list[Clause] = Field(default_factory=list)
    requirements: list[Requirement] = Field(default_factory=list)
    evaluation_criteria: list[Criterion] = Field(default_factory=list)
    required_sections: list[SectionSpec] = Field(default_factory=list)
    deadlines: list[Deadline] = Field(default_factory=list)
    dropped_quotes: int = 0
    notes: list[str] = Field(default_factory=list)
    model: str
    prompt_version: str


class RuleHit(BaseModel):
    rule_id: str
    outcome: Literal["PASS", "INELIGIBLE", "NEEDS_REVIEW"]
    clause: Clause
    company_fact: str
    reason: str


class EligibilityVerdict(BaseModel):
    status: Literal["ELIGIBLE", "INELIGIBLE", "NEEDS_REVIEW"]
    hits: list[RuleHit] = Field(default_factory=list)
    rules_version: str


_LISTS = {
    "eligibility": Clause,
    "requirements": Requirement,
    "evaluation_criteria": Criterion,
    "required_sections": SectionSpec,
    "deadlines": Deadline,
}


def to_brief(
    model_brief: ModelBrief,
    doc_ids: list[uuid.UUID],
    *,
    opportunity_id: uuid.UUID,
    variant: str,
    model: str,
    prompt_version: str,
) -> SolicitationBrief:
    dropped = 0
    out: dict[str, list] = {}
    for field, cls in _LISTS.items():
        items = []
        for item in getattr(model_brief, field):
            c = item.citation
            if not 1 <= c.doc <= len(doc_ids):
                dropped += 1
                continue
            data = item.model_dump(exclude={"citation"})
            if data.get("constraint") is not None:
                data["constraint"] = {
                    k: v for k, v in data["constraint"].items() if v is not None
                } or None
            data["citation"] = Citation(
                document_id=doc_ids[c.doc - 1], page=c.page, quote=c.quote
            )
            items.append(cls(**data))
        out[field] = items
    return SolicitationBrief(
        opportunity_id=opportunity_id,
        variant=variant,
        dropped_quotes=dropped,
        model=model,
        prompt_version=prompt_version,
        **out,
    )


# ---- M2 Discover (system design §6, M2 spec §3.5) ----

Kind = Literal["grant", "sbir", "sttr", "contract"]


class SearchQuery(BaseModel):
    text: str
    kinds: list[Kind] = []
    agencies: list[str] = []
    min_days_to_close: int = 14
    award_min: float | None = None


class SearchPlan(BaseModel):
    intent: str  # the user's goal, restated
    queries: list[SearchQuery]
    must_have: list[str] = []
    exclude: list[str] = []  # agency words to leave out, matched case-insensitively


class Candidate(BaseModel):
    opportunity_id: uuid.UUID
    source_id: str
    title: str
    agency: str
    status: str
    close_at: date | None
    score: float
    reranked: bool = False
    eligibility: Literal["ELIGIBLE", "INELIGIBLE", "NEEDS_REVIEW", "unchecked"] = (
        "unchecked"
    )
    matched_chunks: list[uuid.UUID] = []  # empty in M2 (cards, not chunks)
    why: str = ""


class Rejection(BaseModel):
    candidate: Candidate
    rule_id: str
    reason: str


class VerificationReport(BaseModel):
    passed: list[Candidate]
    rejected: list[Rejection]
    sufficient: bool
    feedback: str


class DiscoverResult(BaseModel):
    request: str
    variant: Literal["B0", "B1"]
    plan: SearchPlan  # the first (approved) plan
    plans: list[SearchPlan]  # every plan executed, in order
    candidates: list[Candidate]
    rejected: list[Rejection]
    iterations: int
    tokens_in: int = 0
    tokens_out: int = 0
    cost_usd: float = 0.0


PreferenceKind = Literal[
    "exclude_agency", "min_award_usd", "avoid_topic", "prefer_topic"
]


class Preference(BaseModel):
    kind: PreferenceKind
    value: str
