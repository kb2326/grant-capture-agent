"""Draft from a real solicitation brief; the draft_section agent tool (M3 spec §3.7)."""

import uuid

from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.contracts import DraftTask, SolicitationBrief, TaskRequirement
from app.draft.b0_long import CorpusCache
from app.draft.corpus import LabeledChunk, load_company_chunks
from app.draft.service import NOTICE, DraftDeps, draft


def task_from_brief(
    brief: SolicitationBrief, section_title: str, max_requirements: int = 8
) -> DraftTask:
    sec = next(
        (
            s
            for s in brief.required_sections
            if s.title.lower() == section_title.lower()
        ),
        None,
    )
    reqs = [
        r for r in brief.requirements if sec and r.citation.page == sec.citation.page
    ] or brief.requirements
    return DraftTask(
        id=f"{brief.opportunity_id}:{section_title}",
        section_title=section_title,
        instructions=f"Write the {section_title} section for this solicitation.",
        requirements=[
            TaskRequirement(id=f"R{i}", text=r.text)
            for i, r in enumerate(reqs[:max_requirements], 1)
        ],
        criteria=[c.name for c in brief.evaluation_criteria],
        opportunity_id=brief.opportunity_id,
    )


def ai_warnings(brief: SolicitationBrief) -> list[str]:
    if (
        brief.prompt_version < "brief_v2"
    ):  # analyzed before AI-use clauses were extracted
        return [
            "AI-use rules were not checked for this solicitation (analyzed before brief_v2); "
            "re-run analyze_opportunity and read the solicitation's rules before using AI-drafted text."
        ]
    return [
        f'{p.text} ("{p.citation.quote}", p. {p.citation.page})'
        for p in brief.ai_policy
    ]


def default_draft_deps(session: Session, settings: Settings) -> DraftDeps:
    from app.analyze.llm import make_client
    from app.discover.llm import GeminiJson
    from rag.chunks import search_chunks
    from rag.embed import GeminiEmbedder

    chunks = load_company_chunks(session)
    by_id = {c.chunk_id: c for c in chunks}
    embedder = GeminiEmbedder(settings)

    def search(query: str) -> list[LabeledChunk]:
        hits = search_chunks(
            session,
            query_text=query,
            query_vec=embedder.embed_query(query),
            k=settings.draft_top_k,
        )
        return [by_id[h.chunk_id] for h in hits if h.chunk_id in by_id]

    client = make_client(settings)
    return DraftDeps(
        settings=settings,
        llm=GeminiJson(
            settings, client=client, thinking_budget=settings.draft_thinking_budget
        ),
        grader=GeminiJson(settings, model_id=settings.model_grader, client=client),
        chunks=chunks,
        search=search,
        cache=CorpusCache(
            client, settings.model_agent, chunks, settings.draft_cache_ttl_s
        ),
    )


def draft_with_cleanup(deps, run):
    """Run drafting and always delete the paid context cache afterwards, even on errors."""
    try:
        return run(deps)
    finally:
        if getattr(deps, "cache", None) is not None:
            deps.cache.delete()


def load_brief(session: Session, opportunity_id: uuid.UUID) -> SolicitationBrief | None:
    from db.models import SolicitationBriefRow

    row = session.get(SolicitationBriefRow, opportunity_id)
    return SolicitationBrief.model_validate(row.brief) if row else None


def draft_section(opportunity_id: str, section_title: str, variant: str = "") -> dict:
    """Draft one proposal section for an analyzed opportunity, citing the company's own documents.

    Args:
        opportunity_id: The opportunity's UUID (run analyze_opportunity first so its brief exists).
        section_title: The section to draft, e.g. "Technical Approach".
        variant: "B0" (whole corpus in context) or "B1" (corrective RAG); empty uses the measured default.
    """
    from app.discover.tools import open_session

    settings = get_settings()
    variant = variant or settings.draft_variant
    if variant not in ("B0", "B1"):
        return {"error": "variant must be B0 or B1"}
    try:
        oid = uuid.UUID(opportunity_id)
    except ValueError:
        return {"error": "opportunity_id must be a UUID"}
    with open_session(settings) as session:
        brief = load_brief(session, oid)
        if brief is None:
            return {
                "error": "no brief for this opportunity yet; call analyze_opportunity first"
            }
        deps = default_draft_deps(session, settings)
        task = task_from_brief(brief, section_title)
        section, _ = draft_with_cleanup(deps, lambda d: draft(d, task, variant))
        titles = {c.chunk_id: c.document_title for c in deps.chunks}
    return {
        "notice": NOTICE,
        "ai_policy_warnings": ai_warnings(brief),
        "paragraphs": [
            {
                "text": p.text,
                "sources": sorted({titles.get(c, "?") for c in p.citations}),
                "supported": p.supported,
            }
            for p in section.paragraphs
        ],
        "gaps": [
            next(r.text for r in task.requirements if r.id == g) for g in section.gaps
        ],
        "cost_usd": round(section.cost_usd, 4),
    }
