"""Planner, refiner and explainer for Discover (M2 spec §3.7). The model proposes; code repairs and constrains."""

import uuid
from pathlib import Path
from string import Template

from pydantic import BaseModel

from app.contracts import (
    Candidate,
    Preference,
    SearchPlan,
    SearchQuery,
    VerificationReport,
)
from app.discover.llm import JsonError, JsonModel

PLAN_PROMPT_VERSION = "discover_plan_v1"
MAX_QUERIES = 5
_PROMPTS = Path(__file__).parent / "prompts"


class WhyItem(BaseModel):
    index: int
    why: str


class WhyList(BaseModel):
    items: list[WhyItem]


def _prompt(name: str, **values: str) -> str:
    # string.Template ($names), so literal braces in prompt text are safe
    return Template((_PROMPTS / name).read_text(encoding="utf-8")).substitute(**values)


def company_brief(profile: dict) -> str:
    caps = "; ".join(profile.get("core_capabilities", []))
    return (
        f"{profile.get('entity_type', 'unknown')} company, {profile.get('employees', '?')} employees, "
        f"state {profile.get('state', '?')}, NAICS {', '.join(profile.get('naics', []))}. "
        f"Capabilities: {caps}."
    )


def _prefs_text(prefs: list[Preference]) -> str:
    return "\n".join(f"- {p.kind}: {p.value}" for p in prefs) or "- none"


def apply_preferences(plan: SearchPlan, prefs: list[Preference]) -> SearchPlan:
    exclude = list(plan.exclude)
    for p in prefs:
        if p.kind == "exclude_agency" and p.value.lower() not in {
            e.lower() for e in exclude
        }:
            exclude.append(p.value)
    floor = max(
        (float(p.value) for p in prefs if p.kind == "min_award_usd"), default=None
    )
    queries = [
        q.model_copy(update={"award_min": max(q.award_min or 0.0, floor)})
        if floor
        else q
        for q in plan.queries
    ]
    return plan.model_copy(update={"exclude": exclude, "queries": queries})


def repair_plan(plan: SearchPlan, request: str) -> SearchPlan:
    queries = [q for q in plan.queries if q.text.strip()][:MAX_QUERIES] or [
        SearchQuery(text=request)
    ]
    exclude = [e.strip() for e in plan.exclude if e.strip()]
    return plan.model_copy(
        update={
            "queries": queries,
            "intent": plan.intent.strip() or request,
            "exclude": exclude,
        }
    )


def make_plan(
    llm: JsonModel, request: str, profile: dict, prefs: list[Preference]
) -> SearchPlan:
    instruction = _prompt(
        "plan_v1.md", company=company_brief(profile), preferences=_prefs_text(prefs)
    )
    try:
        plan = llm.generate(SearchPlan, instruction, request)
    except JsonError:
        plan = SearchPlan(intent=request, queries=[SearchQuery(text=request)])
    return apply_preferences(repair_plan(plan, request), prefs)


def refine_plan(
    llm: JsonModel,
    request: str,
    profile: dict,
    prefs: list[Preference],
    previous: SearchPlan,
    report: VerificationReport,
) -> SearchPlan:
    instruction = _prompt(
        "refine_v1.md",
        company=company_brief(profile),
        preferences=_prefs_text(prefs),
        previous=previous.model_dump_json(),
        feedback=report.feedback,
    )
    try:
        plan = llm.generate(SearchPlan, instruction, request)
    except JsonError:
        return previous
    return apply_preferences(repair_plan(plan, request), prefs)


def explain(
    llm: JsonModel,
    intent: str,
    candidates: list[Candidate],
    cards: dict[uuid.UUID, str],
) -> list[Candidate]:
    if not candidates:
        return candidates
    content = "\n\n".join(
        f"[{i}] {cards.get(c.opportunity_id, c.title)[:1500]}"
        for i, c in enumerate(candidates)
    )
    try:
        out = llm.generate(WhyList, _prompt("why_v1.md", intent=intent), content)
    except JsonError:
        return candidates
    whys = {item.index: item.why.strip() for item in out.items}
    return [
        c.model_copy(update={"why": whys.get(i, "")}) for i, c in enumerate(candidates)
    ]
