"""Section generation shared by B0 and B1: the model cites labels; code maps them to chunk ids and validates."""

from pathlib import Path

from pydantic import BaseModel

from app.contracts import DraftTask, Paragraph
from app.discover.llm import JsonModel
from app.draft.corpus import LabeledChunk, render_chunks

DRAFT_PROMPT_VERSION = "draft_v1"
DRAFT_RULES = (
    Path(__file__).parent / "prompts" / f"{DRAFT_PROMPT_VERSION}.md"
).read_text(encoding="utf-8")


class ModelParagraph(BaseModel):
    text: str
    citations: list[str]


class ModelDraft(BaseModel):
    paragraphs: list[ModelParagraph]
    gaps: list[str]


def task_text(task: DraftTask, gaps: list[str] | None = None) -> str:
    reqs = "\n".join(f"- {r.id}: {r.text}" for r in task.requirements)
    out = f"Section: {task.section_title}\nInstructions: {task.instructions}\nRequirements:\n{reqs}\n"
    if task.criteria:
        out += "Evaluation criteria: " + "; ".join(task.criteria) + "\n"
    if gaps:
        out += (
            "These requirements have NO evidence and must be listed in gaps: "
            + ", ".join(gaps)
            + "\n"
        )
    return out


def validate(draft: ModelDraft, labels: dict[str, LabeledChunk], req_ids: set[str]):
    errors: list[str] = []
    paragraphs = []
    for p in draft.paragraphs:
        ids = []
        for lab in p.citations:
            norm = lab.strip().strip("[]").upper()
            if norm in labels:
                if labels[norm].chunk_id not in ids:
                    ids.append(labels[norm].chunk_id)
            else:
                errors.append(f"unknown citation label {lab!r}")
        paragraphs.append(Paragraph(text=p.text.strip(), citations=ids))
    gaps = [
        g for g in dict.fromkeys(g.strip().upper() for g in draft.gaps) if g in req_ids
    ]
    errors += [
        f"unknown requirement id {g!r} in gaps"
        for g in draft.gaps
        if g.strip().upper() not in req_ids
    ]
    return paragraphs, gaps, errors


def generate_section(
    llm: JsonModel,
    task: DraftTask,
    chunks: list[LabeledChunk],
    *,
    forced_gaps: list[str] | None = None,
    cached_content: str | None = None,
):
    labels = {c.label: c for c in chunks}
    req_ids = {r.id for r in task.requirements}
    content = (
        task_text(task, forced_gaps)
        if cached_content
        else render_chunks(chunks) + "\n\n" + task_text(task, forced_gaps)
    )
    kwargs = {"cached_content": cached_content} if cached_content else {}
    draft = llm.generate(ModelDraft, DRAFT_RULES, content, **kwargs)
    paragraphs, gaps, errors = validate(draft, labels, req_ids)
    invalid = sum(e.startswith("unknown citation") for e in errors)
    if errors:  # one retry, told exactly what was wrong
        draft = llm.generate(
            ModelDraft,
            DRAFT_RULES,
            content + "\n\nFix these problems: " + "; ".join(errors),
            **kwargs,
        )
        paragraphs, gaps, errors = validate(draft, labels, req_ids)
        invalid = sum(
            e.startswith("unknown citation") for e in errors
        )  # stripped by validate
    gaps = list(dict.fromkeys([*gaps, *(forced_gaps or [])]))
    return paragraphs, gaps, invalid
