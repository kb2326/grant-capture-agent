"""Discover verifier rules V1-V5 (system design §8.1). Plain Python; every rejection records its rule."""

from collections import Counter
from datetime import date

from app.contracts import Candidate, Rejection, VerificationReport

RULES_VERSION = "2026-10-09.1"


def _rejection(
    c: Candidate, *, today: date, min_days: int, tau: float | None, seen: set[str]
) -> Rejection | None:
    if c.status not in ("open", "forecasted"):
        return Rejection(candidate=c, rule_id="V1", reason=f"status is {c.status}")
    if c.close_at is not None and (c.close_at - today).days < min_days:
        return Rejection(
            candidate=c,
            rule_id="V2",
            reason=f"closes {c.close_at.isoformat()}, under {min_days} days away",
        )
    if tau is not None and c.reranked and c.score < tau:
        return Rejection(
            candidate=c,
            rule_id="V3",
            reason=f"rerank score {c.score:.2f} below {tau:.2f}",
        )
    if c.eligibility == "INELIGIBLE":
        return Rejection(candidate=c, rule_id="V4", reason="the company is ineligible")
    if c.source_id in seen:
        return Rejection(candidate=c, rule_id="V5", reason="duplicate notice")
    return None


def verify(
    candidates: list[Candidate],
    *,
    today: date,
    min_days_to_close: int,
    tau: float | None,
    k: int,
) -> VerificationReport:
    passed: list[Candidate] = []
    rejected: list[Rejection] = []
    seen: set[str] = set()
    for c in candidates:
        r = _rejection(c, today=today, min_days=min_days_to_close, tau=tau, seen=seen)
        if r:
            rejected.append(r)
        else:
            passed.append(c)
        seen.add(c.source_id)
    counts = Counter(r.rule_id for r in rejected)
    feedback = f"{len(passed)} of {k} needed passed."
    if counts:
        feedback += (
            " Rejected: "
            + ", ".join(f"{rule} x{n}" for rule, n in sorted(counts.items()))
            + "."
        )
    if counts.get("V2"):
        feedback += " Several close too soon: look for later or rolling deadlines."
    if len(passed) < k and not counts:
        feedback += " Too few matches: broaden the queries or use other terms."
    return VerificationReport(
        passed=passed,
        rejected=rejected,
        sufficient=len(passed) >= k,
        feedback=feedback,
    )
