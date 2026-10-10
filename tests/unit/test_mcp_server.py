import asyncio


def test_mcp_server_lists_the_four_tools():
    from mcp_server.server import server

    names = {t.name for t in asyncio.run(server.list_tools())}
    assert names == {
        "search_opportunities",
        "get_brief",
        "check_eligibility",
        "draft_section",
    }


def test_get_brief_rejects_bad_ids():
    from mcp_server.server import get_brief

    assert get_brief("not-a-uuid") == {"error": "opportunity_id must be a UUID"}
