"""ADK 2 workflow: load -> extract -> verify -> rules -> persist (M1 spec §3.5)."""

import uuid
from typing import Literal

from google.adk.workflow import Workflow
from pydantic import BaseModel

from app.analyze.extract import extract_brief
from app.analyze.llm import GeminiBriefModel
from app.analyze.quotes import apply_verification
from app.analyze.service import COMPANY_NAME, load_documents, page_index
from app.config import get_settings
from app.contracts import SolicitationBrief
from app.rules.eligibility import CompanyFacts, decide
from ingest.storage import read_uri


class AnalyzeRequest(BaseModel):
    opportunity_id: str
    variant: Literal["B0", "B1"] = "B0"


def _session():
    from db.session import make_engine, make_session_factory

    return make_session_factory(make_engine(get_settings().database_url))()


def load_node(node_input: AnalyzeRequest) -> dict:
    with _session() as s:
        docs = load_documents(s, uuid.UUID(node_input.opportunity_id), read_uri)
    return {
        "opportunity_id": node_input.opportunity_id,
        "variant": node_input.variant,
        "documents": [d.title for d in docs],
    }


def extract_node(node_input: dict) -> dict:
    settings = get_settings()
    with _session() as s:
        docs = load_documents(s, uuid.UUID(node_input["opportunity_id"]), read_uri)
    brief, usage = extract_brief(
        uuid.UUID(node_input["opportunity_id"]),
        docs,
        node_input["variant"],
        GeminiBriefModel(settings),
        settings,
    )
    return {"brief": brief.model_dump(mode="json"), "cost_usd": usage.cost_usd}


def verify_node(node_input: dict) -> dict:
    brief = SolicitationBrief.model_validate(node_input["brief"])
    with _session() as s:
        docs = load_documents(s, brief.opportunity_id, read_uri)
    return {
        **node_input,
        "brief": apply_verification(brief, page_index(docs)).model_dump(mode="json"),
    }


def rules_node(node_input: dict) -> dict:
    from sqlalchemy import select

    from db.models import CompanyRow

    brief = SolicitationBrief.model_validate(node_input["brief"])
    with _session() as s:
        profile = s.scalar(
            select(CompanyRow.profile).where(CompanyRow.name == COMPANY_NAME)
        )
    verdict = decide(brief.eligibility, CompanyFacts.from_profile(profile))
    return {**node_input, "verdict": verdict.model_dump(mode="json")}


def persist_node(node_input: dict) -> dict:
    from sqlalchemy import select

    from db.models import CompanyRow, EligibilityVerdictRow, SolicitationBriefRow

    brief = node_input["brief"]
    opp = uuid.UUID(brief["opportunity_id"])
    with _session() as s:
        company_id = s.scalar(
            select(CompanyRow.id).where(CompanyRow.name == COMPANY_NAME)
        )
        row = s.get(SolicitationBriefRow, opp) or SolicitationBriefRow(
            opportunity_id=opp
        )
        row.brief, row.model, row.prompt_version = (
            brief,
            brief["model"],
            brief["prompt_version"],
        )
        s.add(row)
        v = s.get(EligibilityVerdictRow, (opp, company_id)) or EligibilityVerdictRow(
            opportunity_id=opp, company_id=company_id
        )
        v.verdict, v.detail, v.rules_version = (
            node_input["verdict"]["status"],
            node_input["verdict"],
            node_input["verdict"]["rules_version"],
        )
        s.add(v)
        s.commit()
    return {
        "verdict": node_input["verdict"]["status"],
        "cost_usd": node_input["cost_usd"],
    }


analyze_workflow = Workflow(
    name="analyze_workflow",
    edges=[("START", load_node, extract_node, verify_node, rules_node, persist_node)],
    input_schema=AnalyzeRequest,
)
