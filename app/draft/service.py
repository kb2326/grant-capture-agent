"""Draft one section with B0 or B1, judge faithfulness, and count cost and latency (M3 spec §3.3-3.7)."""

import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass

from app.config import Settings
from app.contracts import DraftSection, DraftTask
from app.draft.b0_long import CorpusCache, draft_b0
from app.draft.b1_crag import retrieve_evidence
from app.draft.corpus import LabeledChunk
from app.draft.faithfulness import judge
from app.draft.generate import generate_section

NOTICE = (
    "> AI-assisted first draft. Human review and rewrite required before submission. "
    "Check the solicitation's rules on AI use."
)


@dataclass
class DraftDeps:
    settings: Settings
    llm: object  # JsonModel (Flash): queries, drafting, judging
    grader: object  # JsonModel (Flash-Lite)
    chunks: list[LabeledChunk]
    search: Callable[[str], list[LabeledChunk]]
    cache: CorpusCache | None = None


def _tokens(*models) -> tuple[int, int]:
    return sum(m.total_tokens_in for m in models), sum(
        m.total_tokens_out for m in models
    )


def draft(
    deps: DraftDeps, task: DraftTask, variant: str, *, judge_faithfulness: bool = True
):
    s = deps.settings
    start = time.monotonic()
    (fin0, fout0), (gin0, gout0) = _tokens(deps.llm), _tokens(deps.grader)
    trace = []
    if variant == "B0":
        paragraphs, gaps, invalid = draft_b0(deps.llm, task, deps.chunks, deps.cache)
    else:
        evidence, forced, trace = retrieve_evidence(
            deps.llm,
            deps.grader,
            task,
            deps.search,
            min_relevant=s.draft_min_relevant,
            max_rewrites=s.draft_max_rewrites,
        )
        chosen = list({c.chunk_id: c for cs in evidence.values() for c in cs}.values())
        relabeled = [
            LabeledChunk(f"C{i}", c.chunk_id, c.document_title, c.section_path, c.text)
            for i, c in enumerate(chosen, 1)
        ]
        paragraphs, gaps, invalid = generate_section(
            deps.llm, task, relabeled, forced_gaps=forced
        )
    stats = {"claims": 0, "supported": 0}
    if judge_faithfulness:
        paragraphs, stats = judge(
            deps.llm, paragraphs, {c.chunk_id: c.text for c in deps.chunks}
        )
    (fin, fout), (gin, gout) = _tokens(deps.llm), _tokens(deps.grader)
    cost = (
        (fin - fin0) * s.price_agent_input_per_m
        + (fout - fout0) * s.price_agent_output_per_m
        + (gin - gin0) * s.price_grader_input_per_m
        + (gout - gout0) * s.price_grader_output_per_m
    ) / 1e6
    section = DraftSection(
        task_id=task.id,
        variant=variant,
        paragraphs=paragraphs,
        gaps=gaps,  # type: ignore[arg-type]
        retrieval_trace=trace,
        invalid_citations=invalid,
        tokens_in=(fin - fin0) + (gin - gin0),
        tokens_out=(fout - fout0) + (gout - gout0),
        cost_usd=cost,
        latency_s=time.monotonic() - start,
    )
    return section, stats


def to_markdown(
    title: str,
    sections: list[DraftSection],
    tasks: list[DraftTask],
    warnings: list[str],
    titles: dict[uuid.UUID, str] | None = None,
) -> str:
    lines = [NOTICE, "", f"# {title}", ""]
    if warnings:
        lines += [
            "**AI-use rules in this solicitation:**",
            *[f"- {w}" for w in warnings],
            "",
        ]
    by_id = {t.id: t for t in tasks}
    for sec in sections:
        task = by_id.get(sec.task_id)
        lines += [f"## {task.section_title if task else sec.task_id}", ""]
        for p in sec.paragraphs:
            refs = ", ".join((titles or {}).get(c, str(c)[:8]) for c in p.citations)
            flag = (
                ""
                if p.supported is not False
                else " **[unsupported: check before use]**"
            )
            lines += [f"{p.text}{flag} _(sources: {refs or 'none'})_", ""]
        if sec.gaps and task:
            gap_text = {r.id: r.text for r in task.requirements}
            lines += [
                "**Gaps (no evidence found):**",
                *[f"- {g}: {gap_text.get(g, '')}" for g in sec.gaps],
                "",
            ]
    return "\n".join(lines)
