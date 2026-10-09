import json
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from db.models import ChunkRow, DocumentRow, OpportunityRow
from db.session import make_session_factory
from evals.label_app import create_app

pytestmark = pytest.mark.db


def _setup(db_session, tmp_path: Path):
    o = OpportunityRow(
        id=uuid.uuid4(),
        source="grants_gov",
        source_id="l1",
        kind="grant",
        title="Grid",
        agency="DOE",
        summary="",
        url="u",
        status="open",
        naics=[],
        assistance_listings=[],
        eligibility_codes=[],
        raw={},
        content_hash="h",
    )
    db_session.add(o)
    db_session.flush()
    d = DocumentRow(
        opportunity_id=o.id,
        corpus="solicitation",
        gcs_uri="file:///x",
        mime="text/html",
        title="n",
        sha256="s",
        parse_status="parsed",
        page_count=1,
    )
    db_session.add(d)
    db_session.flush()
    db_session.add(
        ChunkRow(
            document_id=d.id,
            ord=1,
            page_start=1,
            page_end=1,
            text="Only nonprofits.",
            n_tokens=4,
        )
    )
    db_session.commit()
    manifest = tmp_path / "m1_sample.json"
    manifest.write_text(
        json.dumps(
            {
                "seed": 1,
                "items": [
                    {
                        "opportunity_id": str(o.id),
                        "source": "grants_gov",
                        "agency": "DOE",
                        "title": "Grid",
                        "requirements": True,
                    }
                ],
            }
        )
    )
    app = create_app(
        make_session_factory(db_session.get_bind()),
        tmp_path,
        manifest,
        labeler="karthick",
    )
    return TestClient(app), o, d


def test_knockout_label_round_trip(db_session, tmp_path: Path):
    client, o, d = _setup(db_session, tmp_path)
    assert client.get("/").status_code == 200
    item = client.get(f"/api/items/{o.id}").json()
    assert item["documents"][0]["pages"][0][
        "text"
    ] == "Only nonprofits." and "model" not in json.dumps(item)
    body = {
        "opportunity_id": str(o.id),
        "verdict": "INELIGIBLE",
        "notes": "",
        "clauses": [
            {
                "quote": "Only nonprofits.",
                "document_id": str(d.id),
                "page": 1,
                "category": "entity_type",
            }
        ],
    }
    assert client.post("/api/labels/knockout", json=body).status_code == 200
    lines = (tmp_path / "knockout.jsonl").read_text(encoding="utf-8").splitlines()
    assert json.loads(lines[0])["_meta"]["labeler"] == "karthick"
    assert json.loads(lines[1])["verdict"] == "INELIGIBLE"
    items = client.get("/api/items").json()
    assert items[0]["knockout_labeled"] is True


def test_invalid_label_is_rejected(db_session, tmp_path: Path):
    client, o, _d = _setup(db_session, tmp_path)
    bad = {"opportunity_id": str(o.id), "verdict": "MAYBE", "clauses": [], "notes": ""}
    assert client.post("/api/labels/knockout", json=bad).status_code == 422
    foreign = {
        "opportunity_id": str(o.id),
        "verdict": "INELIGIBLE",
        "notes": "",
        "clauses": [
            {
                "quote": "x",
                "document_id": str(uuid.uuid4()),
                "page": 1,
                "category": "size",
            }
        ],
    }
    assert client.post("/api/labels/knockout", json=foreign).status_code == 400
