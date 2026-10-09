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


def test_eval_ids_come_from_the_sample_manifest_not_the_labels(tmp_path):
    import json

    from evals.suites.analyze import eval_opportunity_ids

    (tmp_path / "m1_sample.json").write_text(
        json.dumps({"items": [{"opportunity_id": "b"}, {"opportunity_id": "a"}]})
    )
    assert eval_opportunity_ids(tmp_path) == ["a", "b"]


def test_resume_keeps_finished_cases_and_reruns_the_rest():
    from evals.suites.analyze import cases_to_rerun, merge_cases

    old = [
        {"opportunity_id": "a", "error": None, "cost_usd": 0.1},
        {"opportunity_id": "b", "error": "skipped: eval budget reached"},
        {"opportunity_id": "c", "error": "ClientError: 429"},
    ]
    assert cases_to_rerun(old) == ["b", "c"]
    new = [
        {"opportunity_id": "b", "error": None, "cost_usd": 0.1},
        {"opportunity_id": "c", "error": "skipped: eval budget reached"},
    ]
    merged = merge_cases(old, new)
    assert [(c["opportunity_id"], c["error"]) for c in merged] == [
        ("a", None),
        ("b", None),
        ("c", "skipped: eval budget reached"),
    ]


def test_budget_skips_are_not_errors_and_measured_count_is_reported():
    from evals.suites.analyze import evaluate_cases

    case = {
        "opportunity_id": "a",
        "verdict": "ELIGIBLE",
        "clauses": [],
        "requirements": [],
        "quotes_total": 0,
        "quotes_verified": 0,
        "cost_usd": 0.01,
        "latency_s": 1.0,
        "pages": 1,
        "error": None,
    }
    cases = [
        case,
        {"opportunity_id": "b", "error": "skipped: eval budget reached"},
        {"opportunity_id": "c", "error": "ClientError: 429"},
    ]
    m = {
        r.metric: r.value
        for r in evaluate_cases(
            "s", cases, {"a": {"verdict": "ELIGIBLE", "clauses": []}}, {}
        )
    }
    assert m["errors"] == 1.0 and m["cases_measured"] == 1.0


def test_ablation_compares_variants_on_shared_cases_only(tmp_path):

    from evals.ablation import shared_cases

    b0 = [{"opportunity_id": i, "error": None} for i in "abc"]
    b1 = [
        {"opportunity_id": "a", "error": None},
        {"opportunity_id": "b", "error": "skipped: eval budget reached"},
        {"opportunity_id": "c", "error": None},
    ]
    s0, s1 = shared_cases(b0, b1)
    assert (
        [c["opportunity_id"] for c in s0]
        == ["a", "c"]
        == [c["opportunity_id"] for c in s1]
    )


def test_rescore_reapplies_the_rules_offline_from_saved_clauses():
    import json
    from pathlib import Path

    from app.rules.eligibility import CompanyFacts
    from evals.suites.analyze import rescore

    facts = CompanyFacts.from_profile(
        json.loads(Path("data/company/profile.json").read_text(encoding="utf-8"))
    )
    case = {
        "opportunity_id": "a",
        "verdict": "INELIGIBLE",
        "error": None,
        "clauses": [
            {
                "document_id": "11111111-1111-1111-1111-111111111111",
                "page": 1,
                "text": "Higher education",
                "category": "entity_type",
                "constraint": {"allowed": ["university"]},
            },
            {
                "document_id": "11111111-1111-1111-1111-111111111111",
                "page": 1,
                "text": "Small businesses",
                "category": "entity_type",
                "constraint": {"allowed": ["small_business"]},
            },
        ],
    }
    assert rescore([case], facts)[0]["verdict"] == "ELIGIBLE"
    assert rescore(
        [{"opportunity_id": "b", "error": "skipped: eval budget reached"}], facts
    )[0]["error"]


def test_knockout_metrics_with_nothing_to_measure_are_none_not_perfect():
    from evals.suites.analyze import knockout_metrics

    m = knockout_metrics([("ELIGIBLE", "NEEDS_REVIEW")])
    assert (
        m["flagged_recall"] is None
        and m["strict_recall"] is None
        and m["strict_precision"] is None
    )


def test_budget_counts_the_cost_of_failed_cases():
    from evals.suites.analyze import run_cases

    def analyze_one(opp_id):
        exc = RuntimeError("schema failure")
        exc.cost_usd = 0.6
        raise exc

    cases = run_cases(["a", "b", "c"], analyze_one, max_usd=1.0)
    assert (
        cases[0]["cost_usd"] == 0.6
        and cases[1]["error"] == "skipped: eval budget reached"
    )
