"""LLM-drafted dev labels on a different sample (seed + 1). For prompt iteration only (LABELING.md)."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

from app.analyze.llm import GeminiBriefModel
from app.analyze.service import analyze
from app.config import get_settings
from db.session import make_engine, make_session_factory
from evals.sample import draw_sample
from ingest.storage import read_uri


def main(n: int = 20, seed: int = 20261010) -> None:
    settings = get_settings()
    out = Path("evals/data/dev")
    out.mkdir(parents=True, exist_ok=True)
    with make_session_factory(make_engine(settings.database_url))() as session:
        manifest = draw_sample(
            session,
            seed=seed,
            n_grants=n,
            n_sam=0,
            knockout_quota=n // 2,
            n_requirements=0,
        )
        golden = json.loads(
            Path("evals/data/golden/m1_sample.json").read_text(encoding="utf-8")
        )
        golden_ids = {i["opportunity_id"] for i in golden["items"]}
        lines = [
            json.dumps(
                {
                    "_meta": {
                        "drafted_by": settings.model_agent,
                        "seed": seed,
                        "created": datetime.now(UTC).isoformat(),
                        "reviewed": False,
                    }
                }
            )
        ]
        model = GeminiBriefModel(settings)
        for item in manifest["items"]:
            if item["opportunity_id"] in golden_ids:
                continue  # dev and golden never overlap
            r = analyze(
                session,
                uuid.UUID(item["opportunity_id"]),
                model=model,
                read=read_uri,
                settings=settings,
                persist=False,
            )
            lines.append(
                json.dumps(
                    {
                        "opportunity_id": item["opportunity_id"],
                        "verdict": r.verdict.status,
                        "clauses": [
                            {
                                "quote": c.citation.quote,
                                "document_id": str(c.citation.document_id),
                                "page": c.citation.page,
                                "category": c.category,
                            }
                            for c in r.brief.eligibility
                        ],
                    }
                )
            )
    (out / "knockout.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"wrote {len(lines) - 1} dev labels")


if __name__ == "__main__":
    main()
