"""Silver relevance labels for Discover: Flash-Lite grades each pooled card 0/1/2 (M2 spec §4.2)."""

from pydantic import BaseModel

from app.discover.llm import JsonModel
from app.discover.plan import company_brief

LABEL_PROMPT_VERSION = "discover_silver_v1"
MAX_CARD_CHARS = 3_000


class Grade(BaseModel):
    index: int
    grade: int
    reason: str


class Grades(BaseModel):
    items: list[Grade]


INSTRUCTION = (
    "You judge search results for a company looking for U.S. federal funding.\n"
    "Company: {company}\n\n"
    "For each numbered opportunity, grade how well it answers the request:\n"
    "2 = relevant: the company would want to see it for this request;\n"
    "1 = partly relevant: related topic, but a weak fit for the request or the company;\n"
    "0 = not relevant.\n"
    "Judge topic fit only; ignore deadlines and eligibility. Give one short reason per item."
)


def label_query(
    llm: JsonModel,
    query_id: str,
    query_text: str,
    cards: list[tuple[str, str]],
    profile: dict,
) -> list[dict]:
    content = f"Request: {query_text}\n\n" + "\n\n".join(
        f"[{i}] {text[:MAX_CARD_CHARS]}" for i, (_, text) in enumerate(cards)
    )
    out = llm.generate(
        Grades, INSTRUCTION.format(company=company_brief(profile)), content
    )
    labels: dict[int, dict] = {}
    for g in out.items:
        if 0 <= g.index < len(cards) and g.index not in labels:
            labels[g.index] = {
                "query_id": query_id,
                "opportunity_id": cards[g.index][0],
                "grade": min(2, max(0, g.grade)),
                "reason": g.reason.strip(),
            }
    return [labels[i] for i in sorted(labels)]
