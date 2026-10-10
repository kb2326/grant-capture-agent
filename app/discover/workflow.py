"""ADK 2 workflow: plan -> approve_plan (human) -> search -> present (M2 spec §3.7)."""

import json
from typing import Literal

from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.workflow import Workflow, node
from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.contracts import SearchPlan
from app.discover.plan import make_plan
from app.discover.service import run_plan
from app.discover.tools import default_deps, load_company, open_session
from app.memory import load_preferences, preferences_from_edit, save_preferences

APPROVE_WORDS = {"", "ok", "yes", "y", "approve", "approved"}


class DiscoverRequest(BaseModel):
    request: str
    variant: Literal["B0", "B1"] = "B0"


def parse_approval(answer, plan: SearchPlan) -> SearchPlan:
    """'ok' keeps the plan; an edited plan (JSON text or object) replaces it; anything else keeps it."""
    if isinstance(answer, dict):
        answer = json.dumps(answer)
    text = str(answer or "").strip()
    if text.lower() in APPROVE_WORDS:
        return plan
    try:
        return SearchPlan.model_validate_json(text)
    except ValidationError:
        return plan


def plan_node(node_input: DiscoverRequest) -> dict:
    settings = get_settings()
    with open_session(settings) as s:
        deps = default_deps(s, settings, with_checker=False)
        company_id, profile = load_company(s)
        plan = make_plan(
            deps.llm,  # type: ignore[arg-type]
            node_input.request,
            profile,
            load_preferences(s, company_id),
        )
    return {
        "request": node_input.request,
        "variant": node_input.variant,
        "plan": plan.model_dump(mode="json"),
    }


@node(name="approve_plan", rerun_on_resume=True)
async def approve_plan(ctx: Context, node_input: dict):
    if "approve_plan" not in (ctx.resume_inputs or {}):
        yield RequestInput(
            interrupt_id="approve_plan",
            message="Reply 'ok' to run this search plan, or send an edited plan as JSON:\n"
            + json.dumps(node_input["plan"], indent=2),
            response_schema={"type": "string"},
        )
        return
    before = SearchPlan.model_validate(node_input["plan"])
    after = parse_approval(ctx.resume_inputs["approve_plan"], before)
    settings = get_settings()
    with open_session(settings) as s:
        company_id, _ = load_company(s)
        save_preferences(
            s, company_id, preferences_from_edit(before, after), source="plan_edit"
        )
    yield Event(output={**node_input, "plan": after.model_dump(mode="json")})


def search_node(node_input: dict) -> dict:
    settings = get_settings()
    with open_session(settings) as s:
        deps = default_deps(s, settings)
        company_id, profile = load_company(s)
        result = run_plan(
            deps,
            node_input["request"],
            SearchPlan.model_validate(node_input["plan"]),
            variant=node_input["variant"],
            profile=profile,
            prefs=load_preferences(s, company_id),
        )
    return result.model_dump(mode="json")


def present_node(node_input: dict) -> dict:
    keys = ("title", "agency", "close_at", "eligibility", "why", "opportunity_id")
    return {
        "results": [{k: c[k] for k in keys} for c in node_input["candidates"]],
        "iterations": node_input["iterations"],
        "cost_usd": round(node_input["cost_usd"], 4),
    }


discover_workflow = Workflow(
    name="discover_workflow",
    edges=[("START", plan_node, approve_plan, search_node, present_node)],
    input_schema=DiscoverRequest,
)
