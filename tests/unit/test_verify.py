import uuid
from datetime import date

from app.contracts import Candidate
from app.rules.verify import verify

TODAY = date(2026, 10, 9)


def c(**over) -> Candidate:
    data = dict(
        opportunity_id=uuid.uuid4(),
        source_id=uuid.uuid4().hex,
        title="t",
        agency="a",
        status="open",
        close_at=date(2026, 12, 1),
        score=0.8,
        reranked=True,
    )
    data.update(over)
    return Candidate(**data)


def rule_ids(report):
    return [r.rule_id for r in report.rejected]


def test_each_rule_rejects_with_its_id():
    cands = [
        c(status="closed"),  # V1
        c(close_at=date(2026, 10, 15)),  # V2 (6 days < 14)
        c(score=0.1),  # V3
        c(eligibility="INELIGIBLE"),  # V4
        c(source_id="dup"),
        c(source_id="dup"),  # V5 (second one)
        c(close_at=None, status="forecasted"),  # passes: no close date
    ]
    r = verify(cands, today=TODAY, min_days_to_close=14, tau=0.5, k=5)
    assert rule_ids(r) == ["V1", "V2", "V3", "V4", "V5"]
    assert len(r.passed) == 2 and r.sufficient is False
    assert "2 of 5" in r.feedback and "V2" in r.feedback


def test_tau_is_skipped_when_not_reranked_or_unset():
    r = verify(
        [c(score=0.01, reranked=False), c(score=0.01)],
        today=TODAY,
        min_days_to_close=0,
        tau=None,
        k=2,
    )
    assert len(r.passed) == 2 and r.sufficient is True


def test_needs_review_and_unchecked_pass_v4():
    r = verify(
        [c(eligibility="NEEDS_REVIEW"), c()],
        today=TODAY,
        min_days_to_close=0,
        tau=None,
        k=1,
    )
    assert len(r.passed) == 2
