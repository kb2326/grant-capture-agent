"""Analyze one opportunity end to end (M1 spec §3)."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.analyze.extract import LoadedDoc, Usage, extract_brief
from app.analyze.llm import BriefModel
from app.analyze.quotes import PageIndex, PageText, apply_verification
from app.config import Settings, get_settings
from app.contracts import EligibilityVerdict, SolicitationBrief
from app.rules.eligibility import CompanyFacts, decide
from db.models import (
    ChunkRow,
    CompanyRow,
    DocumentRow,
    EligibilityVerdictRow,
    RunRow,
    SolicitationBriefRow,
)
from ingest.textlayer import MIN_PAGE_CHARS, document_kind

COMPANY_NAME = "Lumen Grid Labs"


class NoDocuments(Exception):
    pass


@dataclass
class AnalysisResult:
    brief: SolicitationBrief
    verdict: EligibilityVerdict
    usage: Usage


def load_documents(
    session: Session, opportunity_id: uuid.UUID, read: Callable[[str], bytes]
) -> list[LoadedDoc]:
    docs = session.scalars(
        select(DocumentRow)
        .where(
            DocumentRow.opportunity_id == opportunity_id,
            DocumentRow.parse_status.in_(("parsed", "no_text_layer")),
        )
        .order_by(DocumentRow.created_at)
    ).all()
    loaded = []
    for d in docs:
        chunks = session.scalars(
            select(ChunkRow).where(ChunkRow.document_id == d.id).order_by(ChunkRow.ord)
        ).all()
        pages = [
            (
                c.page_start or c.ord,
                PageText(c.text, len(c.text.replace(" ", "")) >= MIN_PAGE_CHARS),
            )
            for c in chunks
        ]
        kind = document_kind(d.mime, d.title)
        loaded.append(
            LoadedDoc(
                id=d.id,
                title=d.title,
                kind=kind,
                data=read(d.gcs_uri) if kind == "pdf" else b"",
                pages=pages,
            )
        )
    return loaded


def page_index(docs: list[LoadedDoc]) -> PageIndex:
    return {(d.id, n): p for d in docs for n, p in d.pages}


def analyze(
    session: Session,
    opportunity_id: uuid.UUID,
    *,
    variant: str = "B0",
    model: BriefModel,
    read: Callable[[str], bytes],
    settings: Settings,
    persist: bool = True,
) -> AnalysisResult:
    started = datetime.now(UTC)
    docs = load_documents(session, opportunity_id, read)
    if not docs:
        raise NoDocuments(f"opportunity {opportunity_id} has no parsed documents")
    brief, usage = extract_brief(opportunity_id, docs, variant, model, settings)
    brief = apply_verification(brief, page_index(docs))
    company = session.scalar(select(CompanyRow).where(CompanyRow.name == COMPANY_NAME))
    if company is None:
        raise RuntimeError(
            "company profile not seeded: run `python -m ingest seed-company`"
        )
    verdict = decide(brief.eligibility, CompanyFacts.from_profile(company.profile))
    if persist:
        row = session.get(SolicitationBriefRow, opportunity_id) or SolicitationBriefRow(
            opportunity_id=opportunity_id
        )
        row.brief, row.model, row.prompt_version = (
            brief.model_dump(mode="json"),
            brief.model,
            brief.prompt_version,
        )
        session.add(row)
        vrow = session.get(
            EligibilityVerdictRow, (opportunity_id, company.id)
        ) or EligibilityVerdictRow(opportunity_id=opportunity_id, company_id=company.id)
        vrow.verdict, vrow.detail, vrow.rules_version = (
            verdict.status,
            verdict.model_dump(mode="json"),
            verdict.rules_version,
        )
        session.add(vrow)
        session.add(
            RunRow(
                workflow=f"analyze_{brief.variant}",
                started_at=started,
                ended_at=datetime.now(UTC),
                tokens_in=usage.tokens_in,
                tokens_out=usage.tokens_out,
                cost_usd=usage.cost_usd,
                outcome=verdict.status,
            )
        )
        session.commit()
    return AnalysisResult(brief, verdict, usage)


def analyze_opportunity(opportunity_id: str, variant: str = "B0") -> dict:
    """Analyze one funding opportunity: extract its eligibility rules, requirements, scoring criteria,
    required sections and deadlines with page citations, and decide whether the company is eligible.

    Args:
        opportunity_id: The opportunity's UUID.
        variant: "B0" (whole documents, default) or "B1" (page windows).
    """
    from app.analyze.llm import GeminiBriefModel
    from db.session import make_engine, make_session_factory
    from ingest.storage import read_uri

    settings = get_settings()
    with make_session_factory(make_engine(settings.database_url))() as session:
        try:
            r = analyze(
                session,
                uuid.UUID(opportunity_id),
                variant=variant,
                model=GeminiBriefModel(settings),
                read=read_uri,
                settings=settings,
            )
        except NoDocuments as exc:
            return {"status": "no_documents", "message": str(exc)}
    return {
        "verdict": r.verdict.status,
        "deciding_clauses": [
            h.model_dump(mode="json") for h in r.verdict.hits if h.outcome != "PASS"
        ],
        "brief": r.brief.model_dump(mode="json"),
        "cost_usd": round(r.usage.cost_usd, 4),
    }
