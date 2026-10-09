import asyncio

from app.contracts import Preference, SearchPlan, SearchQuery
from app.memory import preference_memory, preferences_from_edit


def test_plan_edit_becomes_preferences():
    before = SearchPlan(intent="x", queries=[SearchQuery(text="a")])
    after = SearchPlan(
        intent="x",
        exclude=["defense"],
        queries=[SearchQuery(text="a", award_min=75_000)],
    )
    assert preferences_from_edit(before, after) == [
        Preference(kind="exclude_agency", value="defense"),
        Preference(kind="min_award_usd", value="75000"),
    ]
    assert preferences_from_edit(before, before) == []


def test_preferences_are_searchable_in_adk_memory():
    prefs = [Preference(kind="exclude_agency", value="defense")]

    async def go():
        memory = await preference_memory(prefs)
        return await memory.search_memory(
            app_name="grant_capture", user_id="company", query="defense"
        )

    found = asyncio.run(go())
    texts = [p.text or "" for m in found.memories for p in (m.content.parts or [])]
    assert any("defense" in t for t in texts)
