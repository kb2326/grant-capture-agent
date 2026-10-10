"""Flash-Lite grader: does this company excerpt support this requirement? (M3 spec §3.5)"""

from typing import Literal

from pydantic import BaseModel

from app.discover.llm import JsonError, JsonModel
from app.draft.corpus import LabeledChunk

GRADES = ("relevant", "partly", "not")
GRADER_PROMPT_VERSION = "grade_v1"
GRADER_RULES = (
    "You check evidence for a proposal. For each numbered company excerpt, grade whether it supports the "
    "requirement: relevant = it states facts that directly answer the requirement; partly = related but does "
    "not answer it; not = unrelated. Outdated documents (an old year in the title, superseded numbers) are "
    "at most partly. Give a short reason."
)


class GradeItem(BaseModel):
    index: int
    grade: Literal["relevant", "partly", "not"]
    reason: str


class GradeList(BaseModel):
    items: list[GradeItem]


def grade_chunks(
    llm: JsonModel, requirement: str, chunks: list[LabeledChunk]
) -> list[tuple[str, str]]:
    if not chunks:
        return []
    content = f"Requirement: {requirement}\n\n" + "\n\n".join(
        f"[{i}] {c.document_title} > {c.section_path.split(' > ')[-1]}\n{c.text[:2000]}"
        for i, c in enumerate(chunks)
    )
    try:
        out = llm.generate(GradeList, GRADER_RULES, content)
    except JsonError:
        return [("not_graded", "")] * len(chunks)
    got = {
        it.index: (it.grade, it.reason)
        for it in out.items
        if 0 <= it.index < len(chunks)
    }
    return [got.get(i, ("not_graded", "")) for i in range(len(chunks))]
