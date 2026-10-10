"""Product API for the local UI (M4 spec §3.1). Live only; every action reports its cost.

Run: uv run uvicorn api.main:app --host 127.0.0.1 --port 8080
"""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from sqlalchemy.exc import OperationalError

from api.budget import SessionBudget
from api.cache import ResultCache
from app.config import get_settings

DB_HINT = "Start the local database: docker compose up -d db"
WEB_DIST = Path(__file__).resolve().parent.parent / "web" / "dist"
# upper-end cost per action, reserved before a live call (measured: search $0.003-0.008,
# analyze $0.04, draft $0.04-0.08); the real cost replaces it afterwards
ESTIMATE_USD = {"discover": 0.01, "analyze": 0.05, "draft": 0.10}


@dataclass
class Tools:
    discover: Callable[..., dict]
    analyze: Callable[..., dict]
    brief: Callable[[str], dict | None]
    draft: Callable[..., dict]


def default_tools() -> Tools:
    def brief(opportunity_id: str) -> dict | None:
        from app.discover.tools import open_session
        from app.draft.tools import load_brief

        with open_session(get_settings()) as s:
            b = load_brief(s, uuid.UUID(opportunity_id))
        return b.model_dump(mode="json") if b else None

    def discover(request: str, variant: str = "B0") -> dict:
        from app.discover.tools import find_opportunities

        # no paid eligibility checks on search: Analyze is an explicit, priced button in the UI
        return find_opportunities(request, variant, check_eligibility=False)

    def analyze(opportunity_id: str) -> dict:
        from app.analyze.service import analyze_opportunity

        return analyze_opportunity(opportunity_id)

    def draft(opportunity_id: str, section_title: str) -> dict:
        from app.draft.tools import draft_section

        return draft_section(opportunity_id, section_title)

    return Tools(discover=discover, analyze=analyze, brief=brief, draft=draft)


class DiscoverBody(BaseModel):
    request: str = Field(min_length=1, max_length=1000)


class AnalyzeBody(BaseModel):
    opportunity_id: str


class DraftBody(BaseModel):
    opportunity_id: str
    section_title: str = Field(min_length=1, max_length=200)


def _hint(error: str) -> str:
    low = error.lower()
    if "analyze" in low or "brief" in low:
        return "Run Analyze on this opportunity first, then draft."
    if "uuid" in low:
        return "Use the opportunity id shown on its card."
    return "Check the API log for details."


def create_app(tools: Tools | None = None, budget_usd: float | None = None) -> FastAPI:
    t = tools or default_tools()
    budget = SessionBudget(
        budget_usd if budget_usd is not None else get_settings().ui_session_budget_usd
    )
    cache = ResultCache()
    app = FastAPI(title="grant-capture local API")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
    )

    def err(status: int, error: str, hint: str) -> JSONResponse:
        return JSONResponse(status_code=status, content={"error": error, "hint": hint})

    @app.exception_handler(Exception)
    def unexpected(_request, exc: Exception) -> JSONResponse:
        return err(
            500,
            f"The action failed: {type(exc).__name__}.",
            "Check the API log for details; try again in a minute.",
        )

    def live(action: str, key: tuple | None, call: Callable[[], dict]):
        if key is not None and (hit := cache.get(key)) is not None:
            return {
                **hit,
                "cost_usd": 0.0,
                "cached": True,
                "session_spent_usd": round(budget.spent_usd, 4),
            }
        estimate = ESTIMATE_USD[action]
        if not budget.reserve(estimate):
            return err(
                402,
                f"Session budget of ${budget.limit_usd:.2f} reached; live calls are paused.",
                "Restart the API to start a new session, or raise ui_session_budget_usd in app/config.py.",
            )
        try:
            out = call()
        except OperationalError:
            budget.settle(estimate, 0.0)  # failed before any model call
            return err(503, "The database is not reachable.", DB_HINT)
        # any other exception keeps the estimate charged: it may have paid before failing
        cost = float(out.get("cost_usd") or 0.0)
        budget.settle(estimate, cost)
        if out.get("status") == "no_documents":  # analyze found nothing to read
            return err(
                400,
                str(out.get("message") or "This opportunity has no stored documents."),
                "This opportunity has no stored solicitation documents to analyze; open another one.",
            )
        if "error" in out:
            return err(400, str(out["error"]), _hint(str(out["error"])))
        if key is not None:
            cache.put(key, out)
        return {
            **out,
            "cost_usd": cost,
            "cached": False,
            "session_spent_usd": round(budget.spent_usd, 4),
        }

    def valid(oid: str) -> bool:
        try:
            uuid.UUID(oid)
            return True
        except ValueError:
            return False

    @app.get("/api/session")
    def session():
        return {"spent_usd": round(budget.spent_usd, 4), "budget_usd": budget.limit_usd}

    @app.post("/api/discover")
    def discover(body: DiscoverBody):
        return live("discover", None, lambda: t.discover(body.request, "B0"))

    @app.get("/api/brief/{opportunity_id}")
    def brief(opportunity_id: str):
        if not valid(opportunity_id):
            return err(400, "opportunity_id must be a UUID", _hint("uuid"))
        try:
            b = t.brief(opportunity_id)
        except OperationalError:
            return err(503, "The database is not reachable.", DB_HINT)
        return (
            b
            if b is not None
            else err(404, "No brief yet for this opportunity.", _hint("analyze"))
        )

    @app.post("/api/analyze")
    def analyze(body: AnalyzeBody):
        if not valid(body.opportunity_id):
            return err(400, "opportunity_id must be a UUID", _hint("uuid"))
        oid = str(uuid.UUID(body.opportunity_id))
        return live("analyze", ("analyze", oid), lambda: t.analyze(oid))

    @app.post("/api/draft")
    def draft(body: DraftBody):
        if not valid(body.opportunity_id):
            return err(400, "opportunity_id must be a UUID", _hint("uuid"))
        oid = str(uuid.UUID(body.opportunity_id))
        key = ("draft", oid, body.section_title.strip().lower())
        return live("draft", key, lambda: t.draft(oid, body.section_title))

    if WEB_DIST.exists():  # the built UI, served by the same process (production image)
        app.mount("/", StaticFiles(directory=WEB_DIST, html=True), name="web")
    return app


app = create_app()
