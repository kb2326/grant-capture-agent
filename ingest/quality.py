"""Post-run data-quality checks. Errors fail the run; warnings are recorded."""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import IngestRunRow, OpportunityRow

THRESHOLDS = {
    "min_seen_ratio": 0.70,
    "max_failed_ratio": 0.05,
    "max_open_missing_close": 0.10,
}


@dataclass(frozen=True)
class QualityIssue:
    check: str
    severity: Literal["error", "warning"]
    message: str


def previous_full_run_seen(session: Session, source: str) -> int | None:
    stats = session.scalar(
        select(IngestRunRow.stats)
        .where(IngestRunRow.stats["source"].astext == source)
        .where(IngestRunRow.stats["limit"].astext.is_(None))
        .order_by(IngestRunRow.started_at.desc(), IngestRunRow.id.desc())
        .limit(1)
    )
    return int(stats["seen"]) if stats and "seen" in stats else None


def check_run(
    session: Session, source: str, *, seen: int, failed: int, previous_seen: int | None
) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    if seen == 0:
        issues.append(QualityIssue("Q1_empty", "error", f"{source}: no records seen"))
    if previous_seen and seen < THRESHOLDS["min_seen_ratio"] * previous_seen:
        issues.append(
            QualityIssue(
                "Q2_volume_drop",
                "error",
                f"{source}: {seen} records vs {previous_seen} last full run",
            )
        )
    if seen and failed / seen > THRESHOLDS["max_failed_ratio"]:
        issues.append(
            QualityIssue(
                "Q3_error_rate", "error", f"{source}: {failed}/{seen} records failed"
            )
        )
    open_q = (
        select(func.count())
        .select_from(OpportunityRow)
        .where(OpportunityRow.source == source, OpportunityRow.status == "open")
    )
    open_total = session.scalar(open_q) or 0
    missing = session.scalar(open_q.where(OpportunityRow.close_at.is_(None))) or 0
    if open_total and missing / open_total > THRESHOLDS["max_open_missing_close"]:
        issues.append(
            QualityIssue(
                "Q4_missing_close_dates",
                "warning",
                f"{source}: {missing}/{open_total} open opportunities lack a close date",
            )
        )
    return issues
