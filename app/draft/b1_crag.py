"""Corrective RAG: per requirement retrieve -> grade -> rewrite <= N -> evidence or gap (M3 spec §3.5)."""

from collections.abc import Callable

from pydantic import BaseModel

from app.contracts import DraftTask, RetrievalAttempt
from app.discover.llm import JsonError, JsonModel
from app.draft.corpus import LabeledChunk
from app.draft.grade import grade_chunks


class ReqQueries(BaseModel):
    requirement_id: str
    queries: list[str]


class QueryPlan(BaseModel):
    items: list[ReqQueries]


class Rewrite(BaseModel):
    query: str


QUERY_RULES = (
    "For each requirement, write 1-2 short search queries (keywords a company's past proposals, "
    "reports or bios would contain). Return items with the requirement id."
)
REWRITE_RULES = (
    "The search for this requirement found no good evidence. Using the grader's reasons, write one "
    "different short search query that could find company documents answering it."
)


def plan_queries(llm: JsonModel, task: DraftTask) -> dict[str, list[str]]:
    content = "\n".join(f"{r.id}: {r.text}" for r in task.requirements)
    try:
        out = llm.generate(QueryPlan, QUERY_RULES, content)
        got = {
            i.requirement_id: [q for q in i.queries if q.strip()][:2] for i in out.items
        }
    except JsonError:
        got = {}
    return {r.id: got.get(r.id) or [r.text] for r in task.requirements}


def rewrite_query(
    llm: JsonModel, requirement: str, query: str, reasons: list[str]
) -> str:
    content = (
        f"Requirement: {requirement}\nPrevious query: {query}\nGrader reasons: "
        + "; ".join(r for r in reasons if r)
    )
    try:
        return (
            llm.generate(Rewrite, REWRITE_RULES, content).query.strip() or requirement
        )
    except JsonError:
        return requirement


def retrieve_evidence(
    llm: JsonModel,
    grader: JsonModel,
    task: DraftTask,
    search: Callable[[str], list[LabeledChunk]],
    *,
    min_relevant: int,
    max_rewrites: int,
):
    evidence: dict[str, list[LabeledChunk]] = {}
    gaps: list[str] = []
    trace: list[RetrievalAttempt] = []
    queries = plan_queries(llm, task)
    for req in task.requirements:
        relevant: dict = {}
        query = " ".join(queries[req.id])
        for attempt in range(max_rewrites + 1):
            hits = search(query)
            grades = grade_chunks(grader, req.text, hits)
            trace.append(
                RetrievalAttempt(
                    requirement_id=req.id,
                    query=query,
                    chunk_ids=[h.chunk_id for h in hits],
                    grades=[gr for gr, _ in grades],
                )
            )
            for h, (gr, _) in zip(hits, grades, strict=True):
                if gr == "relevant":
                    relevant.setdefault(h.chunk_id, h)
            if len(relevant) >= min_relevant or attempt == max_rewrites:
                break
            query = rewrite_query(llm, req.text, query, [r for _, r in grades])
        if relevant:
            evidence[req.id] = list(relevant.values())
        else:
            gaps.append(req.id)
    return evidence, gaps, trace
