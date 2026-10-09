"""Company preferences: a table that persists them and ADK's memory service that the agent can search.

Vertex Memory Bank replaces the in-memory service in M4 (M2 spec §3.8).
"""

import uuid

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.contracts import Preference, SearchPlan
from db.models import CompanyRow, PreferenceRow


def _fmt_amount(v: float) -> str:
    return str(int(v)) if float(v).is_integer() else str(v)


def load_preferences(session: Session, company_id: uuid.UUID) -> list[Preference]:
    out: list[Preference] = []
    company = session.get(CompanyRow, company_id)
    profile_prefs = (company.profile or {}).get("preferences", {}) if company else {}
    if profile_prefs.get("min_award_usd"):
        out.append(
            Preference(
                kind="min_award_usd", value=_fmt_amount(profile_prefs["min_award_usd"])
            )
        )
    out += [
        Preference(kind="exclude_agency", value=a)
        for a in profile_prefs.get("exclude_agencies", [])
    ]
    for row in session.scalars(
        select(PreferenceRow).where(PreferenceRow.company_id == company_id)
    ):
        out.append(Preference(kind=row.kind, value=row.value))  # type: ignore[arg-type]
    unique: dict[tuple[str, str], Preference] = {}
    for p in out:
        unique.setdefault((p.kind, p.value.lower()), p)
    return list(unique.values())


def save_preferences(
    session: Session, company_id: uuid.UUID, prefs: list[Preference], *, source: str
) -> int:
    added = 0
    for p in prefs:
        result = session.execute(
            insert(PreferenceRow)
            .values(
                id=uuid.uuid4(),
                company_id=company_id,
                kind=p.kind,
                value=p.value,
                source=source,
            )
            .on_conflict_do_nothing(constraint="uq_preferences_value")
            .returning(PreferenceRow.id)  # rowcount is -1 here with psycopg
        )
        added += len(result.all())
    session.commit()
    return added


def preferences_from_edit(before: SearchPlan, after: SearchPlan) -> list[Preference]:
    old = {b.lower() for b in before.exclude}
    out = [
        Preference(kind="exclude_agency", value=e)
        for e in after.exclude
        if e.lower() not in old
    ]
    old_floor = max((q.award_min or 0.0 for q in before.queries), default=0.0)
    new_floor = max((q.award_min or 0.0 for q in after.queries), default=0.0)
    if new_floor > old_floor:
        out.append(Preference(kind="min_award_usd", value=_fmt_amount(new_floor)))
    return out


async def preference_memory(
    prefs: list[Preference],
    *,
    app_name: str = "grant_capture",
    user_id: str = "company",
):
    from google.adk.events import Event
    from google.adk.memory import InMemoryMemoryService
    from google.adk.sessions import Session as AdkSession
    from google.genai import types

    events = [
        Event(
            author="user",
            content=types.Content(
                role="user",
                parts=[
                    types.Part.from_text(
                        text=f"Preference {p.kind.replace('_', ' ')}: {p.value}"
                    )
                ],
            ),
        )
        for p in prefs
    ]
    memory = InMemoryMemoryService()
    await memory.add_session_to_memory(
        AdkSession(id="preferences", app_name=app_name, user_id=user_id, events=events)
    )
    return memory
