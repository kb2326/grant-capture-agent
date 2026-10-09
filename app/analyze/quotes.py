"""Quote verification against the text layer (M1 spec §3.4)."""

import re
import unicodedata
import uuid
from dataclasses import dataclass

from app.contracts import Citation, SolicitationBrief

MIN_QUOTE_CHARS = 8
_SQUASH = re.compile(r"[\s\-\u00ad\u2010-\u2014]")


@dataclass(frozen=True)
class PageText:
    text: str
    has_text: bool


PageIndex = dict[tuple[uuid.UUID, int], PageText]


def squash(s: str) -> str:
    return _SQUASH.sub("", unicodedata.normalize("NFKC", s or ""))


def verify(citation: Citation, pages: PageIndex) -> bool:
    current = pages.get((citation.document_id, citation.page))
    if current is None or not current.has_text:
        return False
    quote = squash(citation.quote)
    if len(quote) < MIN_QUOTE_CHARS:
        return False
    if quote in squash(current.text):
        return True
    prev = pages.get((citation.document_id, citation.page - 1))
    nxt = pages.get((citation.document_id, citation.page + 1))
    for a, b in ((current, nxt), (prev, current)):
        if a is not None and b is not None and quote in squash(a.text) + squash(b.text):
            return True
    return False


def apply_verification(brief: SolicitationBrief, pages: PageIndex) -> SolicitationBrief:
    dropped = 0
    clauses = []
    for clause in brief.eligibility:  # possible knockouts are never silently discarded
        clauses.append(
            clause
            if verify(clause.citation, pages)
            else clause.model_copy(update={"constraint": None})
        )
    kept: dict[str, list] = {}
    for field in (
        "requirements",
        "evaluation_criteria",
        "required_sections",
        "deadlines",
    ):
        items = getattr(brief, field)
        good = [i for i in items if verify(i.citation, pages)]
        dropped += len(items) - len(good)
        kept[field] = good
    return brief.model_copy(
        update={
            "eligibility": clauses,
            **kept,
            "dropped_quotes": brief.dropped_quotes + dropped,
        }
    )
