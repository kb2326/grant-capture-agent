"""Draft the Discover query set once with Flash; the user reviews it before labeling (M2 spec §4.1)."""

from typing import Literal

from pydantic import BaseModel

from app.discover.llm import JsonModel
from app.discover.plan import company_brief

N = {"specific": (10, 3), "vague": (5, 2)}  # (golden, dev)


class DraftQuery(BaseModel):
    text: str
    slice: Literal["specific", "vague"]


class DraftQueries(BaseModel):
    items: list[DraftQuery]


INSTRUCTION = (
    "You write test requests for a search tool that finds U.S. federal funding opportunities "
    "(grants, SBIR/STTR, contracts) for this company:\n{company}\n\n"
    "Write 14 'specific' requests (name a technology, program type or agency, like a capture "
    "manager would type) and 8 'vague' requests (broad goals in plain words, like 'funding for "
    "our power electronics work'). Vary the topics across the company's capabilities and "
    "adjacent areas. One sentence each."
)


def draft_queries(llm: JsonModel, profile: dict) -> DraftQueries:
    return llm.generate(
        DraftQueries,
        INSTRUCTION.format(company=company_brief(profile)),
        "Write the requests.",
    )


def split_queries(items: list[DraftQuery]) -> tuple[list[dict], list[dict]]:
    golden: list[dict] = []
    dev: list[dict] = []
    for sl, (n_gold, n_dev) in N.items():
        pool = [q for q in items if q.slice == sl]
        if len(pool) < n_gold + n_dev:
            raise ValueError(f"need {n_gold + n_dev} {sl} queries, got {len(pool)}")
        golden += [
            {"text": q.text, "slice": sl, "split": "golden"} for q in pool[:n_gold]
        ]
        dev += [
            {"text": q.text, "slice": sl, "split": "dev"}
            for q in pool[n_gold : n_gold + n_dev]
        ]
    for i, q in enumerate(golden, 1):
        q["id"] = f"q{i:02d}"
    for i, q in enumerate(dev, 1):
        q["id"] = f"d{i:02d}"
    return golden, dev
