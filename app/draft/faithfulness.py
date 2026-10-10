"""Faithfulness: does each sentence follow from the excerpts it cites? Flash judge, silver (M3 spec §3.6)."""

import re
import uuid
from typing import Literal

from pydantic import BaseModel

from app.contracts import Paragraph
from app.discover.llm import JsonError, JsonModel

JUDGE_RULES = (
    "For each numbered sentence, decide whether its cited excerpts support it: supported = every "
    "fact in the sentence is stated in the excerpts; unsupported = any fact is missing or different; "
    "no_claim = the sentence states no fact (a transition or a heading). A sentence with no excerpts "
    "that states a fact is unsupported."
)
_SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])")


class SentenceVerdict(BaseModel):
    index: int
    label: Literal["supported", "unsupported", "no_claim"]


class VerdictList(BaseModel):
    items: list[SentenceVerdict]


def split_sentences(text: str) -> list[str]:
    out = []
    for line in text.splitlines():
        line = re.sub(r"^\s*([-*•]|\d+\.)\s+", "", line).strip()
        out += [s.strip() for s in _SPLIT.split(line) if s.strip()]
    return out


def judge(
    llm: JsonModel, paragraphs: list[Paragraph], chunk_text: dict[uuid.UUID, str]
):
    rows = [(pi, s) for pi, p in enumerate(paragraphs) for s in split_sentences(p.text)]
    if not rows:
        return paragraphs, {"claims": 0, "supported": 0}
    content = "\n\n".join(
        f"[{i}] {s}\nExcerpts: "
        + (
            " | ".join(chunk_text.get(c, "")[:1500] for c in paragraphs[pi].citations)
            or "(none)"
        )
        for i, (pi, s) in enumerate(rows)
    )
    try:
        got = {
            v.index: v.label
            for v in llm.generate(VerdictList, JUDGE_RULES, content).items
        }
    except JsonError:
        got = {}
    labels = [
        got.get(i, "unsupported") for i in range(len(rows))
    ]  # unjudged claims are not counted as support
    claims = sum(lab != "no_claim" for lab in labels)
    supported = sum(lab == "supported" for lab in labels)
    out = []
    for pi, p in enumerate(paragraphs):
        mine = [lab for (q, _), lab in zip(rows, labels, strict=True) if q == pi]
        out.append(
            p.model_copy(
                update={"supported": not any(lab == "unsupported" for lab in mine)}
            )
        )
    return out, {"claims": claims, "supported": supported}
