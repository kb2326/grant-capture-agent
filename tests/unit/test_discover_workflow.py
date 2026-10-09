from app.contracts import SearchPlan, SearchQuery
from app.discover.workflow import parse_approval

PLAN = SearchPlan(intent="x", queries=[SearchQuery(text="a")])


def test_ok_keeps_the_plan():
    for answer in ("", "ok", "Yes", " approve "):
        assert parse_approval(answer, PLAN) == PLAN


def test_edited_json_replaces_the_plan():
    edited = PLAN.model_copy(update={"exclude": ["defense"]})
    assert parse_approval(edited.model_dump_json(), PLAN) == edited
    assert parse_approval(edited.model_dump(mode="json"), PLAN) == edited


def test_unparseable_answer_keeps_the_plan():
    assert parse_approval("make it better", PLAN) == PLAN


def test_discover_workflow_is_a_workflow():
    from google.adk.workflow import Workflow

    from app.discover.workflow import discover_workflow

    assert isinstance(discover_workflow, Workflow)
