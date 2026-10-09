import json
import uuid

from app.discover.checker import A2AChecker, DirectChecker, parse_verdict

OPP = uuid.uuid4()


def stub_analyze(opportunity_id: str, variant: str = "B0") -> dict:
    return {
        "verdict": "INELIGIBLE",
        "deciding_clauses": [],
        "brief": {},
        "cost_usd": 0.04,
    }


def test_both_transports_give_the_same_verdict():
    direct = DirectChecker(analyze=stub_analyze)
    a2a = A2AChecker(
        "http://unused",
        send=lambda url, text, timeout: json.dumps(stub_analyze(str(OPP))),
    )
    assert direct.check(OPP) == a2a.check(OPP) == "INELIGIBLE"
    assert direct.cost_usd == 0.04


def test_parse_verdict_from_agent_prose_and_failures():
    assert (
        parse_verdict('Result: {"opportunity_id": "x", "verdict": "NEEDS_REVIEW"}')
        == "NEEDS_REVIEW"
    )
    assert parse_verdict('{"status": "no_documents"}') == "unchecked"
    assert parse_verdict("") == "unchecked"


def test_unreachable_a2a_service_is_unchecked():
    assert A2AChecker("http://127.0.0.1:9", timeout=3).check(OPP) == "unchecked"


def test_direct_checker_exception_is_unchecked():
    def boom(opportunity_id, variant="B0"):
        raise RuntimeError("db down")

    assert DirectChecker(analyze=boom).check(OPP) == "unchecked"


def test_analyze_agent_card_is_served():
    from starlette.testclient import TestClient

    from app.analyze.a2a_app import a2a_app

    with TestClient(a2a_app) as client:
        card = client.get("/.well-known/agent-card.json").json()
    assert card["name"] == "analyze_agent"
