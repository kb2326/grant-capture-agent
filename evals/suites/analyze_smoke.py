"""Offline smoke run of the Analyze pipeline on recorded model output (no DB, no network)."""

import json
import uuid
from pathlib import Path

from app.analyze.extract import LoadedDoc, Usage
from app.analyze.quotes import PageText, apply_verification
from app.analyze.service import AnalysisResult, page_index
from app.contracts import ModelBrief, to_brief
from app.rules.eligibility import CompanyFacts, decide
from evals.report import MetricResult
from evals.suites.analyze import case_from_result, evaluate_cases

FIXTURES = Path(__file__).resolve().parents[1] / "fixtures" / "analyze_smoke"


def run() -> list[MetricResult]:
    facts = CompanyFacts.from_profile(
        json.loads(Path("data/company/profile.json").read_text(encoding="utf-8"))
    )
    cases, gold_ko, gold_req = [], {}, {}
    for path in sorted(FIXTURES.glob("case_*.json")):
        f = json.loads(path.read_text(encoding="utf-8"))
        docs = [
            LoadedDoc(
                id=uuid.UUID(d["id"]),
                title=d["title"],
                kind=d["kind"],
                data=b"",
                pages=[
                    (i, PageText(t, True)) for i, t in enumerate(d["pages"], start=1)
                ],
            )
            for d in f["documents"]
        ]
        brief = to_brief(
            ModelBrief.model_validate(f["model_output"]),
            [d.id for d in docs],
            opportunity_id=uuid.UUID(f["opportunity_id"]),
            variant="B0",
            model="recorded",
            prompt_version="brief_v1",
        )
        brief = apply_verification(brief, page_index(docs))
        result = AnalysisResult(brief, decide(brief.eligibility, facts), Usage())
        cases.append(
            case_from_result(
                f["opportunity_id"], result, 0.0, sum(len(d.pages) for d in docs)
            )
        )
        gold_ko[f["opportunity_id"]] = {
            **f["gold_knockout"],
            "opportunity_id": f["opportunity_id"],
        }
        if f["gold_requirements"]:
            gold_req[f["opportunity_id"]] = {"requirements": f["gold_requirements"]}
    return evaluate_cases("analyze_smoke", cases, gold_ko, gold_req)
