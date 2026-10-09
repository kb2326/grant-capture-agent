"""Analyze eval suites (M1 spec §7): knockout, clauses, requirements, quotes, cost/latency."""

import json
import statistics
import time
import uuid
from pathlib import Path

from evals.matching import match_count
from evals.report import MetricResult

TARGETS = {
    "flagged_recall": 0.95,
    "strict_precision": 0.85,
    "requirement_recall": 0.85,
    "quote_fidelity": 1.0,
}


def load_golden(path: Path) -> dict[str, dict]:
    out = {}
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if "_meta" not in rec:
                out[rec["opportunity_id"]] = rec
    return out


def knockout_metrics(pairs: list[tuple[str, str]]) -> dict[str, float]:
    gold_in = [p for g, p in pairs if g == "INELIGIBLE"]
    pred_in = [g for g, p in pairs if p == "INELIGIBLE"]
    return {
        "flagged_recall": (
            sum(p in ("INELIGIBLE", "NEEDS_REVIEW") for p in gold_in) / len(gold_in)
        )
        if gold_in
        else 1.0,
        "strict_recall": (sum(p == "INELIGIBLE" for p in gold_in) / len(gold_in))
        if gold_in
        else 1.0,
        "strict_precision": (sum(g == "INELIGIBLE" for g in pred_in) / len(pred_in))
        if pred_in
        else 1.0,
        "accuracy": (sum(g == p for g, p in pairs) / len(pairs)) if pairs else 0.0,
    }


def evaluate_cases(
    suite: str, cases: list[dict], gold_ko: dict, gold_req: dict
) -> list[MetricResult]:
    ok = [c for c in cases if not c.get("error")]
    pairs = [
        (gold_ko[c["opportunity_id"]]["verdict"], c["verdict"])
        for c in ok
        if c["opportunity_id"] in gold_ko
    ]
    km = knockout_metrics(pairs)
    gold_clauses = [
        dict(document_id=x["document_id"], page=x["page"], text=x["quote"])
        for c in ok
        if c["opportunity_id"] in gold_ko
        for x in gold_ko[c["opportunity_id"]]["clauses"]
    ]
    pred_clauses = [
        x for c in ok if c["opportunity_id"] in gold_ko for x in c["clauses"]
    ]
    req_cases = [c for c in ok if c["opportunity_id"] in gold_req]
    gold_reqs = [
        r for c in req_cases for r in gold_req[c["opportunity_id"]]["requirements"]
    ]
    pred_reqs = [r for c in req_cases for r in c["requirements"]]
    req_hits = match_count(gold_reqs, pred_reqs)
    quotes = sum(c["quotes_total"] for c in ok)
    lat = sorted(c["latency_s"] for c in ok) or [0.0]
    return [
        MetricResult(
            suite,
            "knockout_flagged_recall",
            km["flagged_recall"],
            TARGETS["flagged_recall"],
        ),
        MetricResult(
            suite,
            "knockout_strict_precision",
            km["strict_precision"],
            TARGETS["strict_precision"],
        ),
        MetricResult(suite, "knockout_strict_recall", km["strict_recall"], None),
        MetricResult(suite, "verdict_accuracy", km["accuracy"], None),
        MetricResult(
            suite,
            "clause_recall",
            (match_count(gold_clauses, pred_clauses) / len(gold_clauses))
            if gold_clauses
            else None,
            None,
        ),
        MetricResult(
            suite,
            "requirement_recall",
            (req_hits / len(gold_reqs)) if gold_reqs else None,
            TARGETS["requirement_recall"],
        ),
        MetricResult(
            suite,
            "requirement_precision",
            (req_hits / len(pred_reqs)) if pred_reqs else None,
            None,
        ),
        MetricResult(
            suite,
            "quote_fidelity",
            (sum(c["quotes_verified"] for c in ok) / quotes) if quotes else None,
            TARGETS["quote_fidelity"],
        ),
        MetricResult(
            suite,
            "cost_usd_per_solicitation",
            statistics.mean(c["cost_usd"] for c in ok) if ok else None,
            None,
            higher_is_better=False,
        ),
        MetricResult(
            suite, "latency_p50_s", lat[len(lat) // 2], None, higher_is_better=False
        ),
        MetricResult(
            suite,
            "latency_p95_s",
            lat[min(len(lat) - 1, int(0.95 * len(lat)))],
            None,
            higher_is_better=False,
        ),
        MetricResult(
            suite, "errors", float(len(cases) - len(ok)), 0.0, higher_is_better=False
        ),
    ]


def case_from_result(opportunity_id: str, result, latency_s: float, pages: int) -> dict:
    b = result.brief
    quotes_total = (
        len(b.eligibility)
        + len(b.requirements)
        + len(b.evaluation_criteria)
        + len(b.required_sections)
        + len(b.deadlines)
    )
    unverified_clauses = sum(c.constraint is None for c in b.eligibility)
    return {
        "opportunity_id": opportunity_id,
        "verdict": result.verdict.status,
        "clauses": [
            {
                "document_id": str(c.citation.document_id),
                "page": c.citation.page,
                "text": c.citation.quote,
            }
            for c in b.eligibility
        ],
        "requirements": [
            {
                "document_id": str(r.citation.document_id),
                "page": r.citation.page,
                "text": r.citation.quote,
            }
            for r in b.requirements
        ],
        "quotes_total": quotes_total + b.dropped_quotes,
        "quotes_verified": quotes_total - unverified_clauses,
        "tokens_in": result.usage.tokens_in,
        "tokens_out": result.usage.tokens_out,
        "cost_usd": result.usage.cost_usd,
        "latency_s": latency_s,
        "pages": pages,
        "error": None,
    }


def eval_opportunity_ids(golden_dir: Path) -> list[str]:
    """The sample's opportunities. Runs never need the labels, so they can start before labeling ends."""
    manifest = json.loads((golden_dir / "m1_sample.json").read_text(encoding="utf-8"))
    return sorted(i["opportunity_id"] for i in manifest["items"])


def run_cases(opp_ids: list[str], analyze_one, *, max_usd: float) -> list[dict]:
    """Run cases in order; stop before one more case (as costly as the costliest so far) could exceed max_usd."""
    cases, spent, worst = [], 0.0, 0.0
    for opp_id in opp_ids:
        if spent + worst > max_usd:
            cases.append(
                {"opportunity_id": opp_id, "error": "skipped: eval budget reached"}
            )
            continue
        try:
            case = analyze_one(opp_id)
        except Exception as exc:  # a failed case is reported, never hidden
            case = {"opportunity_id": opp_id, "error": f"{type(exc).__name__}: {exc}"}
        cost = case.get("cost_usd") or 0.0
        spent, worst = spent + cost, max(worst, cost)
        cases.append(case)
    return cases


def cases_to_rerun(cases: list[dict]) -> list[str]:
    return [c["opportunity_id"] for c in cases if c.get("error")]


def merge_cases(old: list[dict], new: list[dict]) -> list[dict]:
    """Earlier results with re-run cases replaced, original order kept."""
    by_id = {c["opportunity_id"]: c for c in new}
    return [by_id.get(c["opportunity_id"], c) for c in old]


def run_variant(
    variant: str,
    *,
    golden_dir: Path = Path("evals/data/golden"),
    out_dir: Path = Path("reports/m1"),
    resume: bool = False,
) -> list[MetricResult]:
    """Run one variant over the sample. resume=True re-runs only skipped/failed cases of the last run."""
    from app.analyze.llm import GeminiBriefModel
    from app.analyze.service import analyze, load_documents
    from app.config import get_settings
    from db.session import make_engine, make_session_factory
    from ingest.storage import read_uri

    settings = get_settings()
    gold_ko = load_golden(golden_dir / "knockout.jsonl")
    gold_req = load_golden(golden_dir / "requirements.jsonl")
    model = GeminiBriefModel(settings)
    with make_session_factory(make_engine(settings.database_url))() as session:

        def analyze_one(opp_id: str) -> dict:
            start = time.monotonic()
            docs = load_documents(session, uuid.UUID(opp_id), read_uri)
            r = analyze(
                session,
                uuid.UUID(opp_id),
                variant=variant,
                model=model,
                read=read_uri,
                settings=settings,
                persist=False,
            )
            return case_from_result(
                opp_id, r, time.monotonic() - start, sum(len(d.pages) for d in docs)
            )

        path = out_dir / f"{variant}-cases.json"
        previous = (
            json.loads(path.read_text(encoding="utf-8"))
            if resume and path.exists()
            else None
        )
        ids = cases_to_rerun(previous) if previous else eval_opportunity_ids(golden_dir)
        cases = run_cases(ids, analyze_one, max_usd=settings.eval_budget_usd)
        if previous:
            cases = merge_cases(previous, cases)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{variant}-cases.json").write_text(
        json.dumps(cases, indent=2), encoding="utf-8"
    )
    spent = sum(c.get("cost_usd") or 0.0 for c in cases)
    print(
        f"{variant}: {len(cases)} cases, estimated cost ${spent:.2f} (cap ${settings.eval_budget_usd:.2f})"
    )
    return evaluate_cases(f"analyze_{variant.lower()}", cases, gold_ko, gold_req)
