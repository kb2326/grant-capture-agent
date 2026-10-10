"""The grant-capture tools over MCP (stdio), usable from Claude Code or any MCP client (M3 spec §3.8)."""

import uuid

from mcp.server.mcpserver import MCPServer

server = MCPServer("grant-capture")


@server.tool()
def search_opportunities(request: str) -> dict:
    """Find open federal funding opportunities that fit Lumen Grid Labs for a plain-English request."""
    from app.discover.tools import find_opportunities

    return find_opportunities(request)


@server.tool()
def get_brief(opportunity_id: str) -> dict:
    """Return the stored solicitation brief (requirements, criteria, sections, deadlines, AI-use rules)."""
    try:
        oid = uuid.UUID(opportunity_id)
    except ValueError:
        return {"error": "opportunity_id must be a UUID"}
    from app.config import get_settings
    from app.discover.tools import open_session
    from app.draft.tools import load_brief

    with open_session(get_settings()) as s:
        brief = load_brief(s, oid)
    return (
        brief.model_dump(mode="json")
        if brief
        else {"error": "no brief yet; call check_eligibility first"}
    )


@server.tool()
def check_eligibility(opportunity_id: str) -> dict:
    """Analyze an opportunity and return only the eligibility verdict and the deciding clauses."""
    from app.analyze.service import analyze_opportunity

    out = analyze_opportunity(opportunity_id)
    return {
        k: out[k] for k in ("verdict", "deciding_clauses", "cost_usd") if k in out
    } or out


@server.tool()
def draft_section(opportunity_id: str, section_title: str) -> dict:
    """Draft one proposal section from the company's documents, with sources, gaps and the AI-use notice."""
    from app.draft.tools import draft_section as _draft

    return _draft(opportunity_id, section_title)
