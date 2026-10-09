"""Seeded, stratified sample of opportunities for the M1 golden sets (M1 spec §6.1)."""

import argparse
import json
import random
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from db.models import ChunkRow, DocumentRow, OpportunityRow

KNOCKOUT_TERMS = (
    "nonprofit",
    "non-profit",
    "institutions of higher education",
    "state governments",
    "tribal",
    "phase ii",
    "cost share",
    "cost-share",
)


def _pick(
    pool: list, k: int, rng: random.Random, taken: set, agency_count: dict, cap: int
) -> list:
    out = []
    for opp in rng.sample(pool, len(pool)):
        if len(out) == k:
            break
        if opp.id in taken or agency_count.get(opp.agency, 0) >= cap:
            continue
        out.append(opp)
        taken.add(opp.id)
        agency_count[opp.agency] = agency_count.get(opp.agency, 0) + 1
    return out


def draw_sample(
    session: Session,
    *,
    seed: int,
    n_grants: int = 28,
    n_sam: int = 12,
    knockout_quota: int = 15,
    per_agency: int = 4,
    n_requirements: int = 10,
) -> dict:
    rng = random.Random(seed)
    term_filter = or_(*[func.lower(ChunkRow.text).contains(t) for t in KNOCKOUT_TERMS])
    grants = session.scalars(
        select(OpportunityRow)
        .where(
            OpportunityRow.source == "grants_gov",
            OpportunityRow.id.in_(
                select(DocumentRow.opportunity_id).where(
                    DocumentRow.parse_status == "parsed"
                )
            ),
        )
        .order_by(OpportunityRow.source_id)
    ).all()
    grants_ko_ids = set(
        session.scalars(
            select(DocumentRow.opportunity_id)
            .join(ChunkRow, ChunkRow.document_id == DocumentRow.id)
            .where(term_filter)
        ).all()
    )
    sam = session.scalars(
        select(OpportunityRow)
        .where(OpportunityRow.source == "sam_gov", OpportunityRow.status == "open")
        .order_by(OpportunityRow.source_id)
    ).all()
    sam_ko_ids = {
        o.id for o in sam if any(t in (o.summary or "").lower() for t in KNOCKOUT_TERMS)
    }

    taken, agency_count = set(), {}
    ko_grants = round(knockout_quota * n_grants / (n_grants + n_sam))
    ko_sam = knockout_quota - ko_grants
    chosen_grants = _pick(
        [o for o in grants if o.id in grants_ko_ids],
        ko_grants,
        rng,
        taken,
        agency_count,
        per_agency,
    )
    chosen_grants += _pick(
        grants, n_grants - len(chosen_grants), rng, taken, agency_count, per_agency
    )
    chosen_sam = _pick(
        [o for o in sam if o.id in sam_ko_ids],
        ko_sam,
        rng,
        taken,
        agency_count,
        per_agency,
    )
    chosen_sam += _pick(
        sam, n_sam - len(chosen_sam), rng, taken, agency_count, per_agency
    )

    pages = dict(
        session.execute(
            select(
                DocumentRow.opportunity_id, func.sum(DocumentRow.page_count)
            ).group_by(DocumentRow.opportunity_id)
        ).all()
    )
    by_length = sorted(chosen_grants, key=lambda o: (pages.get(o.id) or 0, str(o.id)))
    step = len(by_length) / n_requirements
    req_ids = {by_length[int(i * step)].id for i in range(n_requirements)}

    items = [
        {
            "opportunity_id": str(o.id),
            "source": o.source,
            "agency": o.agency,
            "title": o.title,
            "requirements": o.id in req_ids,
        }
        for o in rng.sample(
            chosen_grants + chosen_sam, len(chosen_grants) + len(chosen_sam)
        )
    ]
    return {
        "seed": seed,
        "created": datetime.now(UTC).isoformat(),
        "terms": list(KNOCKOUT_TERMS),
        "items": items,
    }


def main(argv: list[str] | None = None) -> int:
    from app.config import get_settings
    from db.session import make_engine, make_session_factory

    p = argparse.ArgumentParser()
    p.add_argument("milestone", choices=["m1"])
    p.add_argument("--seed", type=int, default=20261009)
    p.add_argument("--out", default="evals/data/golden/m1_sample.json")
    args = p.parse_args(argv)
    with make_session_factory(make_engine(get_settings().database_url))() as session:
        manifest = draw_sample(session, seed=args.seed)
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"wrote {args.out}: {len(manifest['items'])} items")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
