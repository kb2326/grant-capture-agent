"""Draft metrics scored by code from the corpus plan, plus silver faithfulness (M3 spec §5)."""

import json
from pathlib import Path

from evals.report import MetricResult
from evals.suites.discover import percentile

MIN_GAIN = 0.05
FREE_COST_USD, FREE_LATENCY_S = 0.005, 2.0
QUALITY = ("gap_recall", "evidence_recall", "faithfulness")


def score_section(
    task: dict, section: dict, chunk_text: dict[str, str], chunk_kind: dict[str, str]
) -> dict:
    gold_gaps = {r["id"] for r in task["requirements"] if "gap_terms" in r}
    flagged = set(section["gaps"])
    cited = [c for p in section["paragraphs"] for c in p["citations"]]
    valid = [c for c in cited if c in chunk_text]
    covered = 0
    for r in task["requirements"]:
        if (
            "evidence" in r
            and r["id"] not in flagged
            and any(any(e in chunk_text[c] for e in r["evidence"]) for c in valid)
        ):
            covered += 1
    given = section.get("given", [])
    return {
        "gold_gaps": len(gold_gaps),
        "flagged": len(flagged),
        "true_gaps": len(flagged & gold_gaps),
        "covered": covered,
        "supported_reqs": len(task["requirements"]) - len(gold_gaps),
        # labels the model invented were removed by validation; they still count against validity
        "citations": len(cited) + int(section.get("invalid_citations", 0)),
        "valid_citations": len(valid),
        "distractor_citations": sum(
            chunk_kind.get(c) in ("outdated", "off_topic") for c in valid
        ),
        "given": len(given),
        "cited_given": len(set(given) & set(valid)),
    }


def _ratio(num: float, den: float) -> float | None:
    return None if den == 0 else num / den


def summarize_draft(rows: list[dict]) -> dict:
    def tot(k):
        return sum(r.get(k, 0) for r in rows)

    lat = [r["latency_s"] for r in rows if "latency_s" in r]
    return {
        "gap_recall": _ratio(tot("true_gaps"), tot("gold_gaps")),
        "gap_precision": _ratio(tot("true_gaps"), tot("flagged")),
        "evidence_recall": _ratio(tot("covered"), tot("supported_reqs")),
        "citation_validity": _ratio(tot("valid_citations"), tot("citations")),
        "distractor_rate": _ratio(tot("distractor_citations"), tot("valid_citations")),
        "faithfulness": _ratio(tot("supported"), tot("claims")),
        "context_precision": _ratio(tot("cited_given"), tot("given")),
        "p50_s": percentile(lat, 0.5),
        "p95_s": percentile(lat, 0.95),
        "cost_usd": _ratio(tot("cost_usd"), len(rows)),
        "n": len(rows),
    }


def _within(simple, rich, free) -> bool:
    if simple is None or rich is None:
        return True
    return rich <= 2 * simple or rich - simple < free


def keep_b1(b0: dict, b1: dict) -> bool:
    gain = any(
        b0[m] is not None and b1[m] is not None and b1[m] - b0[m] >= MIN_GAIN
        for m in QUALITY
    )
    return (
        gain
        and _within(b0["cost_usd"], b1["cost_usd"], FREE_COST_USD)
        and _within(b0["p95_s"], b1["p95_s"], FREE_LATENCY_S)
    )


FIXTURES = Path("evals/fixtures/draft_smoke")


def run_smoke() -> list[MetricResult]:
    tasks = {
        t["id"]: t
        for t in map(
            json.loads,
            (FIXTURES / "tasks.jsonl").read_text(encoding="utf-8").splitlines(),
        )
    }
    data = json.loads((FIXTURES / "sections.json").read_text(encoding="utf-8"))
    chunks = json.loads((FIXTURES / "chunks.json").read_text(encoding="utf-8"))
    rows = [
        {
            **score_section(tasks[s["task_id"]], s, chunks["text"], chunks["kind"]),
            **s["stats"],
        }
        for s in data
    ]
    s = summarize_draft(rows)
    return [
        MetricResult("draft_smoke", "gap_recall", s["gap_recall"], 0.5),
        MetricResult("draft_smoke", "evidence_recall", s["evidence_recall"], 0.5),
    ]
