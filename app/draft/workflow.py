"""ADK 2 workflow: load brief -> draft sections -> approve_draft (human) -> export Markdown (M3 spec §3.7)."""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from google.adk.agents.context import Context
from google.adk.events.event import Event
from google.adk.events.request_input import RequestInput
from google.adk.workflow import Workflow, node
from pydantic import BaseModel

from app.config import get_settings
from app.contracts import DraftSection, DraftTask

APPROVE = {"", "ok", "yes", "y", "approve", "approved"}


class DraftRequest(BaseModel):
    opportunity_id: str
    sections: list[str] = []  # empty: every required section in the brief
    variant: Literal["B0", "B1", ""] = ""


def parse_draft_approval(answer) -> Literal["approve", "reject"]:
    return "approve" if str(answer or "").strip().lower() in APPROVE else "reject"


def draft_node(node_input: DraftRequest) -> dict:
    from app.discover.tools import open_session
    from app.draft.service import draft
    from app.draft.tools import (
        ai_warnings,
        default_draft_deps,
        draft_with_cleanup,
        load_brief,
        task_from_brief,
    )

    settings = get_settings()
    with open_session(settings) as s:
        brief = load_brief(s, uuid.UUID(node_input.opportunity_id))
        if brief is None:
            return {
                "error": "no brief; run analyze_opportunity first",
                "sections": [],
                "tasks": [],
            }
        deps = default_draft_deps(s, settings)
        titles = (
            node_input.sections or [sec.title for sec in brief.required_sections][:6]
        )
        tasks = [task_from_brief(brief, t) for t in titles]
        variant = node_input.variant or settings.draft_variant
        sections = draft_with_cleanup(
            deps, lambda d: [draft(d, t, variant)[0] for t in tasks]
        )
        chunk_titles = {str(c.chunk_id): c.document_title for c in deps.chunks}
    return {
        "opportunity_id": node_input.opportunity_id,
        "warnings": ai_warnings(brief),
        "tasks": [t.model_dump(mode="json") for t in tasks],
        "sections": [x.model_dump(mode="json") for x in sections],
        "chunk_titles": chunk_titles,
    }


@node(name="approve_draft", rerun_on_resume=True)
async def approve_draft(ctx: Context, node_input: dict):
    if "approve_draft" not in (ctx.resume_inputs or {}):
        yield RequestInput(
            interrupt_id="approve_draft",
            message=f"{len(node_input.get('sections', []))} section(s) drafted. Reply 'ok' to export, or 'reject'.",
            response_schema={"type": "string"},
        )
        return
    yield Event(
        output={
            **node_input,
            "decision": parse_draft_approval(ctx.resume_inputs["approve_draft"]),
        }
    )


def export_node(node_input: dict) -> dict:
    from app.draft.service import to_markdown

    if node_input.get("decision") != "approve":
        return {"exported": None, "status": "rejected"}
    sections = [DraftSection.model_validate(x) for x in node_input["sections"]]
    tasks = [DraftTask.model_validate(x) for x in node_input["tasks"]]
    titles = {uuid.UUID(k): v for k, v in node_input["chunk_titles"].items()}
    path = (
        Path("data/drafts")
        / f"{node_input['opportunity_id']}-{datetime.now(UTC):%Y%m%dT%H%M%S}.md"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        to_markdown(
            f"Draft for {node_input['opportunity_id']}",
            sections,
            tasks,
            node_input["warnings"],
            titles,
        ),
        encoding="utf-8",
    )
    return {"exported": str(path), "status": "approved"}


draft_workflow = Workflow(
    name="draft_workflow",
    edges=[("START", draft_node, approve_draft, export_node)],
    input_schema=DraftRequest,
)
