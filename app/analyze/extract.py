"""Brief extraction: B0 whole documents, B1 page windows (M1 spec §3.3)."""

import uuid
from dataclasses import dataclass
from pathlib import Path

from google.genai import types

from app.analyze.llm import BriefModel
from app.analyze.quotes import PageText, squash
from app.config import Settings
from app.contracts import ModelBrief, SolicitationBrief, to_brief

PROMPT_VERSION = "brief_v1"
PDF_PAGE_TOKENS = 258
_PROMPT = Path(__file__).with_name("prompts") / f"{PROMPT_VERSION}.md"
_LIST_FIELDS = (
    "eligibility",
    "requirements",
    "evaluation_criteria",
    "required_sections",
    "deadlines",
)


@dataclass
class LoadedDoc:
    id: uuid.UUID
    title: str
    kind: str  # pdf | html | docx | text
    data: bytes
    pages: list[tuple[int, PageText]]


@dataclass
class Usage:
    calls: int = 0
    tokens_in: int = 0
    tokens_out: int = 0
    latency_s: float = 0.0
    cost_usd: float = 0.0


def load_instruction() -> str:
    return _PROMPT.read_text(encoding="utf-8")


def estimate_tokens(docs: list[LoadedDoc]) -> int:
    total = 0
    for d in docs:
        if d.kind == "pdf":
            total += PDF_PAGE_TOKENS * len(d.pages)
        else:
            total += sum(len(p.text) for _, p in d.pages) // 4
    return total


def _paged(k: int, pages: list[tuple[int, PageText]]) -> str:
    body = "\n".join(f"[PAGE {n}]\n{p.text}" for n, p in pages)
    return f"<<<DOCUMENT {k} BEGIN>>>\n{body}\n<<<DOCUMENT {k} END>>>"


def b0_parts(docs: list[LoadedDoc]) -> list[types.Part]:
    parts: list[types.Part] = []
    for k, d in enumerate(docs, start=1):
        parts.append(types.Part.from_text(text=f"DOCUMENT {k}: {d.title}"))
        if d.kind == "pdf":
            parts.append(
                types.Part.from_bytes(data=d.data, mime_type="application/pdf")
            )
        else:
            parts.append(types.Part.from_text(text=_paged(k, d.pages)))
    return parts


def b1_calls(docs: list[LoadedDoc], size: int, overlap: int) -> list[list[types.Part]]:
    calls: list[list[types.Part]] = []
    step = max(size - overlap, 1)
    for k, d in enumerate(docs, start=1):
        for start in range(0, len(d.pages), step):
            window = d.pages[start : start + size]
            calls.append(
                [
                    types.Part.from_text(text=f"DOCUMENT {k}: {d.title}"),
                    types.Part.from_text(text=_paged(k, window)),
                ]
            )
            if start + size >= len(d.pages):
                break
    return calls


def merge(briefs: list[ModelBrief]) -> ModelBrief:
    merged: dict[str, list] = {f: [] for f in _LIST_FIELDS}
    seen: dict[str, set] = {f: set() for f in _LIST_FIELDS}
    for b in briefs:
        for f in _LIST_FIELDS:
            for item in getattr(b, f):
                key = (item.citation.doc, squash(item.citation.quote))
                if key not in seen[f]:
                    seen[f].add(key)
                    merged[f].append(item)
    return ModelBrief(**merged)


def extract_brief(
    opportunity_id: uuid.UUID,
    docs: list[LoadedDoc],
    variant: str,
    model: BriefModel,
    settings: Settings,
) -> tuple[SolicitationBrief, Usage]:
    notes: list[str] = []
    if variant == "B0" and estimate_tokens(docs) > settings.analyze_context_budget:
        variant = "B1"
        notes.append(
            f"switched to B1: estimated tokens exceed context budget {settings.analyze_context_budget}"
        )
    instruction = load_instruction()
    calls = (
        [b0_parts(docs)]
        if variant == "B0"
        else b1_calls(docs, settings.analyze_window_pages, overlap=1)
    )
    usage, results = Usage(), []
    for parts in calls:
        r = model.extract(parts, instruction)
        results.append(r.brief)
        usage.calls += 1
        usage.tokens_in += r.tokens_in
        usage.tokens_out += r.tokens_out
        usage.latency_s += r.latency_s
    usage.cost_usd = (
        usage.tokens_in * settings.price_agent_input_per_m
        + usage.tokens_out * settings.price_agent_output_per_m
    ) / 1_000_000
    brief = to_brief(
        merge(results),
        [d.id for d in docs],
        opportunity_id=opportunity_id,
        variant=variant,
        model=model.model_id,
        prompt_version=PROMPT_VERSION,
    )
    return brief.model_copy(update={"notes": notes}), usage
