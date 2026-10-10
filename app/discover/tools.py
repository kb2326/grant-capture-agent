"""Agent-facing Discover tools and the default wiring from settings."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyze.service import COMPANY_NAME
from app.config import Settings, get_settings
from app.discover.checker import make_checker
from app.discover.llm import GeminiJson
from app.discover.service import DiscoverDeps, discover
from app.memory import load_preferences
from db.models import CompanyRow
from rag.embed import COLUMNS, make_embedder
from rag.rerank import make_reranker


def load_company(session: Session) -> tuple[uuid.UUID, dict]:
    row = session.execute(
        select(CompanyRow.id, CompanyRow.profile).where(CompanyRow.name == COMPANY_NAME)
    ).one()
    return row.id, row.profile


def default_deps(
    session: Session, settings: Settings, *, with_checker: bool = True
) -> DiscoverDeps:
    company_id, _ = load_company(session)
    return DiscoverDeps(
        session=session,
        settings=settings,
        embedder=make_embedder(settings.discover_embedding, settings),
        column=COLUMNS[settings.discover_embedding],
        reranker=make_reranker(settings.discover_rerank, settings),
        llm=GeminiJson(settings),
        checker=make_checker(settings) if with_checker else None,
        company_id=company_id,
        tau=settings.discover_tau,
    )


def open_session(settings: Settings) -> Session:
    from db.session import make_engine, make_session_factory

    return make_session_factory(make_engine(settings.database_url))()


def find_opportunities(request: str, variant: str = "B0") -> dict:
    """Find open funding opportunities that fit the company for a plain-English request.

    Args:
        request: What to look for, e.g. "SBIR work on grid-forming inverters".
        variant: "B0" (single pass, default) or "B1" (plan, execute, verify and refine).
    """
    if variant not in ("B0", "B1"):
        return {"error": "variant must be B0 or B1"}
    settings = get_settings()
    with open_session(settings) as session:
        deps = default_deps(session, settings)
        company_id, profile = load_company(session)
        result = discover(
            deps,
            request,
            variant=variant,  # type: ignore[arg-type]
            profile=profile,
            prefs=load_preferences(session, company_id),
        )
    return {
        "plan": result.plan.model_dump(mode="json"),
        "candidates": [
            {
                "opportunity_id": str(c.opportunity_id),
                "title": c.title,
                "agency": c.agency,
                "close_at": c.close_at.isoformat() if c.close_at else None,
                "eligibility": c.eligibility,
                "why": c.why,
            }
            for c in result.candidates
        ],
        "iterations": result.iterations,
        "cost_usd": round(result.cost_usd, 4),
    }


def remembered_preferences() -> dict:
    """List the company's remembered search preferences (excluded agencies, minimum award, topics)."""
    settings = get_settings()
    with open_session(settings) as session:
        company_id, _ = load_company(session)
        return {
            "preferences": [
                p.model_dump() for p in load_preferences(session, company_id)
            ]
        }
