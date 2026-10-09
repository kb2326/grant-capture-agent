import json
import uuid
from pathlib import Path

from app.analyze.extract import LoadedDoc
from app.analyze.quotes import PageText
from evals.ai_label import LabelerOutput, label_item, write_labels

DOC = LoadedDoc(
    id=uuid.uuid4(),
    title="nofo.html",
    kind="html",
    data=b"",
    pages=[
        (
            1,
            PageText(
                "Eligible applicants: Only nonprofit organizations may apply.", True
            ),
        ),
        (2, PageText("Applicants must submit a budget justification.", True)),
    ],
)


def _output(**over) -> LabelerOutput:
    data = {
        "verdict": "INELIGIBLE",
        "rationale": "Only nonprofits may apply; the company is for-profit.",
        "clauses": [
            {
                "doc": 1,
                "page": 1,
                "quote": "Only nonprofit organizations may apply.",
                "category": "entity_type",
            },
            {
                "doc": 1,
                "page": 2,
                "quote": "an invented clause that is not there",
                "category": "other",
            },
        ],
        "requirements": [
            {
                "doc": 1,
                "page": 2,
                "text": "Applicants must submit a budget justification.",
            }
        ],
    }
    data.update(over)
    return LabelerOutput.model_validate(data)


def test_label_item_maps_documents_and_flags_unverified_quotes():
    opp = str(uuid.uuid4())
    ko, req = label_item(opp, [DOC], _output(), want_requirements=True)
    assert ko["verdict"] == "INELIGIBLE" and ko["opportunity_id"] == opp
    assert ko["clauses"][0] == {
        "quote": "Only nonprofit organizations may apply.",
        "document_id": str(DOC.id),
        "page": 1,
        "category": "entity_type",
        "quote_verified": True,
    }
    assert ko["clauses"][1]["quote_verified"] is False
    assert (
        req["requirements"][0]["document_id"] == str(DOC.id)
        and req["requirements"][0]["quote_verified"]
    )


def test_requirements_only_for_items_marked_for_them():
    _, req = label_item(str(uuid.uuid4()), [DOC], _output(), want_requirements=False)
    assert req is None


def test_out_of_range_document_is_dropped():
    out = _output(
        clauses=[{"doc": 5, "page": 1, "quote": "x" * 20, "category": "size"}]
    )
    ko, _ = label_item(str(uuid.uuid4()), [DOC], out, want_requirements=False)
    assert ko["clauses"] == []


def test_write_labels_adds_silver_header_once_and_skips_labeled(tmp_path: Path):
    meta = {"labeler": "ai:test-model", "silver": True}
    write_labels(
        tmp_path / "knockout.jsonl",
        [{"opportunity_id": "a", "verdict": "ELIGIBLE"}],
        meta,
    )
    write_labels(
        tmp_path / "knockout.jsonl",
        [{"opportunity_id": "b", "verdict": "ELIGIBLE"}],
        meta,
    )
    lines = [
        json.loads(x)
        for x in (tmp_path / "knockout.jsonl").read_text(encoding="utf-8").splitlines()
    ]
    assert lines[0]["_meta"]["silver"] is True and [
        x.get("opportunity_id") for x in lines[1:]
    ] == ["a", "b"]
