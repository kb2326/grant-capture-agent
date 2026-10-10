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
    c = TestClient(create_app(t, budget_usd=0.05))
    c.post("/api/analyze", json={"opportunity_id": OID})  # 0.04
    c.post(
        "/api/draft", json={"opportunity_id": OID, "section_title": "Approach"}
    )  # 0.06 total
    blocked = c.post("/api/discover", json={"request": "x"})
    assert (
        blocked.status_code == 402
        and calls["discover"] == 0
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
