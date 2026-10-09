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


def test_run_cases_stops_before_the_budget_is_exceeded():
    from evals.suites.analyze import run_cases

    calls = []

    def analyze_one(opp_id):
        calls.append(opp_id)
        return {"opportunity_id": opp_id, "cost_usd": 0.30, "error": None}

    cases = run_cases(["a", "b", "c", "d", "e"], analyze_one, max_usd=1.0)
    # after 3 cases ($0.90) one more could reach $1.20, so it stops
    assert calls == ["a", "b", "c"]
    assert [c["error"] for c in cases[3:]] == ["skipped: eval budget reached"] * 2


def test_run_cases_records_failures_and_keeps_going():
    from evals.suites.analyze import run_cases

    def analyze_one(opp_id):
        if opp_id == "bad":
            raise RuntimeError("boom")
        return {"opportunity_id": opp_id, "cost_usd": 0.01, "error": None}

    cases = run_cases(["bad", "ok"], analyze_one, max_usd=1.0)
    assert cases[0]["error"] == "RuntimeError: boom" and cases[1]["error"] is None
