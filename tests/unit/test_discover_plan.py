import uuid
from datetime import date

from app.contracts import (
    Candidate,
    Preference,
    SearchPlan,
    SearchQuery,
    VerificationReport,
)
from app.discover.llm import JsonError
from app.discover.plan import (
    WhyItem,
    WhyList,
    apply_preferences,
    explain,
    make_plan,
    refine_plan,
)

PROFILE = {
    "entity_type": "for_profit",
    "employees": 32,
    "state": "CO",
    "naics": ["541715"],
    "core_capabilities": ["Grid-forming inverter controls"],
}


class FakeLLM:
    model_id, total_tokens_in, total_tokens_out = "fake", 0, 0

    def __init__(self, *outputs):
        self.outputs, self.instructions = list(outputs), []

    def generate(self, schema, instruction, content):
        self.instructions.append(instruction)
        out = self.outputs.pop(0)
        if isinstance(out, Exception):
            raise out
        return out


def test_plan_falls_back_to_request_on_model_failure():
    plan = make_plan(FakeLLM(JsonError("bad")), "grid inverters", PROFILE, [])
    assert plan.intent == "grid inverters"
    assert [q.text for q in plan.queries] == ["grid inverters"]


def test_plan_is_repaired_empty_blank_and_too_many_queries():
    empty = SearchPlan(intent="x", queries=[])
    assert [q.text for q in make_plan(FakeLLM(empty), "req", PROFILE, []).queries] == [
        "req"
    ]
    blank = SearchPlan(
        intent="x", queries=[SearchQuery(text="  "), SearchQuery(text="ok")]
    )
    assert [q.text for q in make_plan(FakeLLM(blank), "req", PROFILE, []).queries] == [
        "ok"
    ]
    many = SearchPlan(intent="x", queries=[SearchQuery(text=f"q{i}") for i in range(8)])
    assert len(make_plan(FakeLLM(many), "req", PROFILE, []).queries) == 5


def test_preferences_reach_prompt_and_become_filters():
    prefs = [
        Preference(kind="exclude_agency", value="defense"),
        Preference(kind="min_award_usd", value="50000"),
    ]
    llm = FakeLLM(
        SearchPlan(intent="x", queries=[SearchQuery(text="a", award_min=10_000)])
    )
    plan = make_plan(llm, "req", PROFILE, prefs)
    assert "defense" in llm.instructions[0] and "Grid-forming" in llm.instructions[0]
    assert plan.exclude == ["defense"] and plan.queries[0].award_min == 50_000


def test_apply_preferences_does_not_duplicate_or_lower():
    plan = SearchPlan(
        intent="x",
        exclude=["Defense"],
        queries=[SearchQuery(text="a", award_min=90_000)],
    )
    out = apply_preferences(
        plan,
        [
            Preference(kind="exclude_agency", value="defense"),
            Preference(kind="min_award_usd", value="50000"),
        ],
    )
    assert out.exclude == ["Defense"] and out.queries[0].award_min == 90_000


def test_refine_sends_feedback_and_falls_back_to_previous():
    prev = SearchPlan(intent="x", queries=[SearchQuery(text="a")])
    report = VerificationReport(
        passed=[], rejected=[], sufficient=False, feedback="0 of 5 needed passed."
    )
    llm = FakeLLM(JsonError("bad"))
    assert refine_plan(llm, "req", PROFILE, [], prev, report) == prev
    assert "0 of 5 needed passed." in llm.instructions[0]


def test_explain_sets_why_by_index_and_ignores_failures():
    cands = [
        Candidate(
            opportunity_id=uuid.uuid4(),
            source_id=str(i),
            title="t",
            agency="a",
            status="open",
            close_at=date(2027, 1, 1),
            score=1.0,
        )
        for i in range(2)
    ]
    cards = {x.opportunity_id: "card text" for x in cands}
    llm = FakeLLM(WhyList(items=[WhyItem(index=1, why="Matches inverters.")]))
    assert [x.why for x in explain(llm, "x", cands, cards)] == [
        "",
        "Matches inverters.",
    ]
    failed = explain(FakeLLM(JsonError("bad")), "x", cands, cards)
    assert [x.why for x in failed] == ["", ""]
