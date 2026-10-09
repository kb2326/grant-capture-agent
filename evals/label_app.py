"""Local labeling page for the golden sets (M1 spec §6.2). Never shows model output."""

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.contracts import Category
from db.models import ChunkRow, DocumentRow, OpportunityRow


class ClauseLabel(BaseModel):
    quote: str = Field(min_length=1)
    document_id: uuid.UUID
    page: int = Field(ge=1)
    category: Category


class KnockoutLabel(BaseModel):
    opportunity_id: uuid.UUID
    verdict: Literal["ELIGIBLE", "INELIGIBLE", "NEEDS_REVIEW"]
    clauses: list[ClauseLabel] = []
    notes: str = ""


class RequirementItem(BaseModel):
    text: str = Field(min_length=1)
    document_id: uuid.UUID
    page: int = Field(ge=1)


class RequirementsLabel(BaseModel):
    opportunity_id: uuid.UUID
    requirements: list[RequirementItem]


def _latest(path: Path) -> dict[str, dict]:
    if not path.exists():
        return {}
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        if "_meta" not in rec:
            out[rec["opportunity_id"]] = rec  # last write wins
    return out


def create_app(
    session_factory, golden_dir: Path, manifest_path: Path, labeler: str
) -> FastAPI:
    app = FastAPI(title="grant-capture labeling")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    ko_path, req_path = golden_dir / "knockout.jsonl", golden_dir / "requirements.jsonl"

    def append(path: Path, record: dict) -> None:
        golden_dir.mkdir(parents=True, exist_ok=True)
        new = not path.exists()
        with path.open("a", encoding="utf-8") as fh:
            if new:
                fh.write(
                    json.dumps(
                        {
                            "_meta": {
                                "labeler": labeler,
                                "created": datetime.now(UTC).isoformat(),
                                "manifest": manifest_path.name,
                                "seed": manifest.get("seed"),
                            }
                        }
                    )
                    + "\n"
                )
            fh.write(json.dumps(record) + "\n")

    def doc_ids_of(opportunity_id: uuid.UUID) -> set[uuid.UUID]:
        with session_factory() as s:
            return set(
                s.scalars(
                    select(DocumentRow.id).where(
                        DocumentRow.opportunity_id == opportunity_id
                    )
                ).all()
            )

    @app.get("/", response_class=HTMLResponse)
    def index() -> str:
        return (Path(__file__).with_name("label_ui.html")).read_text(encoding="utf-8")

    @app.get("/api/items")
    def items() -> list[dict]:
        ko, req = _latest(ko_path), _latest(req_path)
        return [
            {
                **i,
                "knockout_labeled": i["opportunity_id"] in ko,
                "requirements_labeled": i["opportunity_id"] in req,
            }
            for i in manifest["items"]
        ]

    @app.get("/api/items/{opportunity_id}")
    def item(opportunity_id: uuid.UUID) -> dict:
        with session_factory() as s:
            o = s.get(OpportunityRow, opportunity_id)
            if o is None:
                raise HTTPException(404, "unknown opportunity")
            docs = []
            for d in s.scalars(
                select(DocumentRow)
                .where(DocumentRow.opportunity_id == o.id)
                .order_by(DocumentRow.created_at)
            ).all():
                chunks = s.scalars(
                    select(ChunkRow)
                    .where(ChunkRow.document_id == d.id)
                    .order_by(ChunkRow.ord)
                ).all()
                docs.append(
                    {
                        "id": str(d.id),
                        "title": d.title,
                        "parse_status": d.parse_status,
                        "pages": [
                            {
                                "page": c.page_start,
                                "heading": c.section_path,
                                "text": c.text,
                            }
                            for c in chunks
                        ],
                    }
                )
            return {
                "id": str(o.id),
                "title": o.title,
                "agency": o.agency,
                "source": o.source,
                "url": o.url,
                "close_at": o.close_at.isoformat() if o.close_at else None,
                "summary": o.summary,
                "documents": docs,
                "knockout": _latest(ko_path).get(str(o.id)),
                "requirements": _latest(req_path).get(str(o.id)),
            }

    @app.get("/api/documents/{document_id}/file")
    def document_file(document_id: uuid.UUID):
        from ingest.storage import (
            read_uri,  # local files only; served for opening PDFs in the browser
        )

        with session_factory() as s:
            d = s.get(DocumentRow, document_id)
        if d is None or not d.gcs_uri.startswith("file:"):
            raise HTTPException(404, "not a local file")
        from urllib.parse import urlparse
        from urllib.request import url2pathname

        read_uri(d.gcs_uri)  # raises if missing
        return FileResponse(url2pathname(urlparse(d.gcs_uri).path), filename=d.title)

    @app.post("/api/labels/knockout")
    def save_knockout(label: KnockoutLabel) -> dict:
        allowed = doc_ids_of(label.opportunity_id)
        if any(c.document_id not in allowed for c in label.clauses):
            raise HTTPException(400, "clause cites a document of another opportunity")
        append(
            ko_path,
            {
                **label.model_dump(mode="json"),
                "labeler": labeler,
                "labeled_at": datetime.now(UTC).isoformat(),
            },
        )
        return {"saved": True}

    @app.post("/api/labels/requirements")
    def save_requirements(label: RequirementsLabel) -> dict:
        allowed = doc_ids_of(label.opportunity_id)
        if any(r.document_id not in allowed for r in label.requirements):
            raise HTTPException(
                400, "requirement cites a document of another opportunity"
            )
        append(
            req_path,
            {
                **label.model_dump(mode="json"),
                "labeler": labeler,
                "labeled_at": datetime.now(UTC).isoformat(),
            },
        )
        return {"saved": True}

    return app
