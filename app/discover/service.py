"""Discover: plan -> execute (hybrid search + rerank) -> verify -> [refine] (M2 spec §3.7)."""

import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings
from app.contracts import (
    Candidate,
    DiscoverResult,
    Preference,
    Rejection,
    SearchPlan,
    SearchQuery,
)
from app.discover.checker import EligibilityChecker, cached_verdicts
from app.discover.llm import JsonModel
from app.discover.plan import explain, make_plan, refine_plan
from app.rules.verify import verify
from db.models import OpportunityCardRow, OpportunityRow
from rag.embed import Embedder
from rag.rerank import RerankDoc, Reranker
from rag.search import Filters, hybrid_search

RERANK_DEPTH = 30
PRESENT = 10


def load_rows(
    session: Session, ids: list[uuid.UUID]
) -> dict[uuid.UUID, tuple[OpportunityRow, str]]:
    rows = session.execute(
        select(OpportunityRow, OpportunityCardRow.text)
        .join(
            OpportunityCardRow, OpportunityCardRow.opportunity_id == OpportunityRow.id
        )
        .where(OpportunityRow.id.in_(ids))
    )
    return {o.id: (o, text) for o, text in rows}


_search = hybrid_search  # seams for unit tests
_load = load_rows


@dataclass
class DiscoverDeps:
    session: Session | None
    settings: Settings
    embedder: Embedder
    column: str
    reranker: Reranker
    llm: JsonModel | None = None
    checker: EligibilityChecker | None = None
    company_id: uuid.UUID | None = None
    tau: float | None = None
    today: date = field(default_factory=date.today)


def filters_for(query: SearchQuery, plan: SearchPlan, today: date) -> Filters:
    return Filters(
        kinds=list(query.kinds),
        min_close=today + timedelta(days=query.min_days_to_close),
        exclude_agencies=list(plan.exclude),
        award_min=query.award_min,
    )


def execute(deps: DiscoverDeps, plan: SearchPlan) -> list[Candidate]:
    best: dict[uuid.UUID, float] = {}
    for q in plan.queries:
        vec = deps.embedder.embed_query(q.text)
        for h in _search(
            deps.session,
            query_text=q.text,
            query_vec=vec,
            column=deps.column,
            filters=filters_for(q, plan, deps.today),
        ):
            best[h.opportunity_id] = max(best.get(h.opportunity_id, 0.0), h.score)
    fused = sorted(best.items(), key=lambda kv: (-kv[1], str(kv[0])))[:RERANK_DEPTH]
    rows = _load(deps.session, [i for i, _ in fused])
    fused = [(i, s) for i, s in fused if i in rows]
    ranked = deps.reranker.rerank(
        plan.intent, [RerankDoc(str(i), rows[i][0].title, rows[i][1]) for i, _ in fused]
    )
    order: list[tuple[uuid.UUID, float, bool]] = []
    if ranked:
        order = [(uuid.UUID(i), s, True) for i, s in ranked if uuid.UUID(i) in rows]
    seen = {i for i, _, _ in order}
    # anything the ranker dropped keeps its fused order after the reranked ones
    order += [(i, s, False) for i, s in fused if i not in seen]
    return [
        Candidate(
            opportunity_id=i,
            source_id=rows[i][0].source_id,
            title=rows[i][0].title,
            agency=rows[i][0].agency,
            status=rows[i][0].status,
            close_at=rows[i][0].close_at,
            score=s,
            reranked=r,
        )
        for i, s, r in order
    ]


def _check_eligibility(deps: DiscoverDeps, cands: list[Candidate]) -> None:
    if deps.company_id is None or deps.session is None:
        return
    cached = cached_verdicts(
        deps.session, deps.company_id, [c.opportunity_id for c in cands]
    )
    for c in cands:
        if c.opportunity_id in cached:
            c.eligibility = cached[c.opportunity_id]  # type: ignore[assignment]
    if deps.checker is None:
        return
    unchecked = [c for c in cands if c.eligibility == "unchecked"]
    for c in unchecked[: deps.settings.discover_v4_max_checks]:
        c.eligibility = deps.checker.check(c.opportunity_id)  # type: ignore[assignment]


def _key(plan: SearchPlan) -> tuple:
    return tuple(sorted(q.text.strip().lower() for q in plan.queries))


def run_plan(
    deps: DiscoverDeps,
    request: str,
    plan: SearchPlan,
    *,
    variant: Literal["B0", "B1"],
    profile: dict,
    prefs: list[Preference],
    explain_top: bool = True,
) -> DiscoverResult:
    s = deps.settings
    llm_in0 = deps.llm.total_tokens_in if deps.llm else 0
    llm_out0 = deps.llm.total_tokens_out if deps.llm else 0
    emb0, rank0 = deps.embedder.tokens, deps.reranker.calls
    plans: list[SearchPlan] = [plan]
    passed: dict[uuid.UUID, Candidate] = {}
    rejected: list[Rejection] = []
    current, iterations = plan, 0
    while True:
        iterations += 1
        cands = execute(deps, current)
        _check_eligibility(deps, cands)
        report = verify(
            cands,
            today=deps.today,
            min_days_to_close=min(q.min_days_to_close for q in current.queries),
            tau=deps.tau,
            k=s.discover_k,
        )
        for c in report.passed:
            passed.setdefault(c.opportunity_id, c)  # earlier iterations stay first
        rejected += report.rejected
        if (
            variant == "B0"
            or deps.llm is None
            or len(passed) >= s.discover_k
            or iterations >= s.discover_max_iterations
        ):
            break
        new = refine_plan(deps.llm, request, profile, prefs, current, report)
        if _key(new) in {_key(p) for p in plans}:
            break
        plans.append(new)
        current = new
    final = list(passed.values())[:PRESENT]
    if explain_top and deps.llm is not None and final:
        loaded = _load(deps.session, [c.opportunity_id for c in final])
        final = explain(
            deps.llm, plan.intent, final, {i: t for i, (_, t) in loaded.items()}
        )
    tin = (deps.llm.total_tokens_in - llm_in0) if deps.llm else 0
    tout = (deps.llm.total_tokens_out - llm_out0) if deps.llm else 0
    emb_tokens = deps.embedder.tokens - emb0 if deps.embedder.name == "gemini" else 0
    cost = (
        tin * s.price_agent_input_per_m / 1e6
        + tout * s.price_agent_output_per_m / 1e6
        + emb_tokens * s.price_embedding_per_m / 1e6
        + (deps.reranker.calls - rank0) * s.price_rank_per_1k / 1000
    )
    return DiscoverResult(
        request=request,
        variant=variant,
        plan=plan,
        plans=plans,
        candidates=final,
        rejected=rejected,
        iterations=iterations,
        tokens_in=tin,
        tokens_out=tout,
        cost_usd=cost,
    )


def discover(
    deps: DiscoverDeps,
    request: str,
    *,
    variant: Literal["B0", "B1"],
    profile: dict,
    prefs: list[Preference],
    approve: Callable[[SearchPlan], SearchPlan] | None = None,
    explain_top: bool = True,
) -> DiscoverResult:
    if deps.llm is None:
        raise ValueError("discover needs a planner model")
    plan = make_plan(deps.llm, request, profile, prefs)
    if approve is not None:
        plan = approve(plan)
    return run_plan(
        deps,
        request,
        plan,
        variant=variant,
        profile=profile,
        prefs=prefs,
        explain_top=explain_top,
    )
