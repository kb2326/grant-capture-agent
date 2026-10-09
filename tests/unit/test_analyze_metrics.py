import pytest

from evals.suites.analyze import knockout_metrics


def test_knockout_metrics_flagged_vs_strict():
    pairs = [
        ("INELIGIBLE", "INELIGIBLE"),
        ("INELIGIBLE", "NEEDS_REVIEW"),
        ("ELIGIBLE", "INELIGIBLE"),
        ("ELIGIBLE", "ELIGIBLE"),
    ]
    m = knockout_metrics(pairs)
    assert m["flagged_recall"] == 1.0 and m["strict_recall"] == 0.5
    assert m["strict_precision"] == 0.5 and m["accuracy"] == pytest.approx(0.5)
