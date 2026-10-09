from app.agent import app, root_agent


def test_root_agent_identity():
    assert root_agent.name == "grant_capture_agent"
    assert app.root_agent is root_agent


def test_root_agent_has_no_demo_tools():
    tool_names = {getattr(t, "__name__", str(t)) for t in root_agent.tools}
    assert "get_weather" not in tool_names
    assert "get_current_time" not in tool_names


def test_root_agent_exposes_analyze_tools():
    names = {getattr(t, "__name__", "") for t in root_agent.tools}
    assert {"analyze_opportunity", "ask_solicitation"} <= names


def test_analyze_workflow_is_a_workflow():
    from google.adk.workflow import Workflow

    from app.analyze.workflow import analyze_workflow

    assert isinstance(analyze_workflow, Workflow)
