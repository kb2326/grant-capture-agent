from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from api.main import Tools, create_app

OID = "6b462ee3-1c2e-47b2-818b-bf02b93e3043"


def tools(**over):
    calls = {"discover": 0, "analyze": 0, "draft": 0}

    def discover(request, variant="B0"):
        calls["discover"] += 1
        return {"plan": {}, "candidates": [], "cost_usd": 0.01}

    def analyze(opportunity_id):
        calls["analyze"] += 1
        return {"verdict": "ELIGIBLE", "brief": {}, "cost_usd": 0.04}

    def brief(opportunity_id):
        return {"opportunity_id": opportunity_id} if opportunity_id == OID else None

    def draft(opportunity_id, section_title):
        calls["draft"] += 1
        return {"notice": "> AI", "paragraphs": [], "gaps": [], "cost_usd": 0.02}

    t = Tools(discover=discover, analyze=analyze, brief=brief, draft=draft)
    for k, v in over.items():
        setattr(t, k, v)
    return t, calls


def test_live_actions_report_cost_and_session_total():
    t, _ = tools()
    c = TestClient(create_app(t, budget_usd=1.0))
    r = c.post("/api/discover", json={"request": "inverters"}).json()
    assert (
        r["cost_usd"] == 0.01
        and r["cached"] is False
        and r["session_spent_usd"] == 0.01
    )
    assert c.get("/api/session").json() == {"spent_usd": 0.01, "budget_usd": 1.0}


def test_repeat_analyze_is_cached_and_free():
    t, calls = tools()
    c = TestClient(create_app(t, budget_usd=1.0))
    c.post("/api/analyze", json={"opportunity_id": OID})
    r = c.post("/api/analyze", json={"opportunity_id": OID}).json()
    assert calls["analyze"] == 1 and r["cached"] is True and r["cost_usd"] == 0.0
    assert r["session_spent_usd"] == 0.04


def test_budget_blocks_live_calls_but_serves_cache():
    t, calls = tools()
    c = TestClient(create_app(t, budget_usd=0.10))
    c.post(
        "/api/analyze", json={"opportunity_id": OID}
    )  # reserves 0.05, settles at 0.04
    blocked = c.post(
        "/api/draft", json={"opportunity_id": OID, "section_title": "Approach"}
    )  # 0.04 + 0.10 estimate > 0.10: refused before calling
    assert (
        blocked.status_code == 402
        and calls["draft"] == 0
        and "budget" in blocked.json()["error"].lower()
    )
    assert c.post("/api/analyze", json={"opportunity_id": OID}).json()["cached"] is True


def test_tool_error_is_400_with_hint_and_not_cached():
    t, _ = tools(
        draft=lambda o, s: {
            "error": "no brief for this opportunity yet; call analyze_opportunity first"
        }
    )
    c = TestClient(create_app(t, budget_usd=1.0))
    r = c.post("/api/draft", json={"opportunity_id": OID, "section_title": "Approach"})
    assert r.status_code == 400 and "analyze" in r.json()["hint"].lower()
    assert c.get("/api/session").json()["spent_usd"] == 0.0


def test_database_down_gives_503_with_docker_hint():
    def down(*a, **k):
        raise OperationalError("select 1", {}, Exception("connection refused"))

    t, _ = tools(discover=down)
    r = TestClient(create_app(t, budget_usd=1.0)).post(
        "/api/discover", json={"request": "x"}
    )
    assert r.status_code == 503 and "docker compose up -d db" in r.json()["hint"]


def test_brief_is_free_and_404_when_missing():
    t, _ = tools()
    c = TestClient(create_app(t, budget_usd=1.0))
    assert c.get(f"/api/brief/{OID}").json()["opportunity_id"] == OID
    missing = c.get("/api/brief/00000000-0000-0000-0000-000000000000")
    assert missing.status_code == 404 and "analyze" in missing.json()["hint"].lower()


def test_bad_uuid_is_400():
    t, _ = tools()
    r = TestClient(create_app(t, budget_usd=1.0)).post(
        "/api/analyze", json={"opportunity_id": "nope"}
    )
    assert r.status_code == 400


def test_no_documents_is_a_400_with_hint_not_a_success():
    t, _ = tools(
        analyze=lambda oid: {"status": "no_documents", "message": "no documents stored"}
    )
    c = TestClient(create_app(t, budget_usd=1.0))
    r = c.post("/api/analyze", json={"opportunity_id": OID})
    assert r.status_code == 400 and "documents" in r.json()["hint"].lower()
    assert (
        c.post("/api/analyze", json={"opportunity_id": OID}).status_code == 400
    )  # not cached


def test_ui_search_skips_paid_eligibility_checks(monkeypatch):
    import app.discover.tools as dt
    from api.main import default_tools

    seen = {}

    def fake(request, variant="B0", check_eligibility=True):
        seen.update(request=request, check=check_eligibility)
        return {"plan": {}, "candidates": [], "cost_usd": 0.0}

    monkeypatch.setattr(dt, "find_opportunities", fake)
    default_tools().discover("inverters", "B0")
    assert seen == {"request": "inverters", "check": False}


def test_unexpected_tool_error_is_json_500_and_still_counts_the_estimate():
    def boom(oid):
        raise RuntimeError("429 from Gemini")

    t, _ = tools(analyze=boom)
    c = TestClient(create_app(t, budget_usd=1.0), raise_server_exceptions=False)
    r = c.post("/api/analyze", json={"opportunity_id": OID})
    assert r.status_code == 500 and r.json()["hint"]
    assert c.get("/api/session").json()["spent_usd"] > 0  # may have paid before failing


def test_cache_key_normalizes_uuid_spelling():
    t, calls = tools()
    c = TestClient(create_app(t, budget_usd=1.0))
    c.post("/api/analyze", json={"opportunity_id": OID})
    r = c.post("/api/analyze", json={"opportunity_id": OID.upper()}).json()
    assert r["cached"] is True and calls["analyze"] == 1


def test_oversized_request_is_rejected_before_any_call():
    t, calls = tools()
    c = TestClient(create_app(t, budget_usd=1.0))
    r = c.post("/api/discover", json={"request": "x" * 5000})
    assert r.status_code == 422 and calls["discover"] == 0
