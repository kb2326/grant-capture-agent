import uuid

from app.contracts import ModelBrief, to_brief

OPP = uuid.UUID("11111111-1111-1111-1111-111111111111")
D1, D2 = uuid.uuid4(), uuid.uuid4()


def _model_brief(doc_for_req: int) -> ModelBrief:
    return ModelBrief.model_validate(
        {
            "eligibility": [
                {
                    "category": "size",
                    "citation": {
                        "doc": 1,
                        "page": 3,
                        "quote": "500 or fewer employees",
                    },
                    "constraint": {"max_employees": 500},
                }
            ],
            "requirements": [
                {
                    "text": "Proposals shall not exceed 15 pages",
                    "citation": {
                        "doc": doc_for_req,
                        "page": 7,
                        "quote": "shall not exceed 15 pages",
                    },
                }
            ],
            "evaluation_criteria": [],
            "required_sections": [],
            "deadlines": [],
        }
    )


def test_doc_index_maps_to_document_id():
    brief = to_brief(
        _model_brief(2),
        [D1, D2],
        opportunity_id=OPP,
        variant="B0",
        model="m",
        prompt_version="v",
    )
    assert brief.eligibility[0].citation.document_id == D1
    assert brief.requirements[0].citation.document_id == D2
    assert brief.dropped_quotes == 0


def test_out_of_range_doc_index_is_dropped_and_counted():
    brief = to_brief(
        _model_brief(7),
        [D1, D2],
        opportunity_id=OPP,
        variant="B0",
        model="m",
        prompt_version="v",
    )
    assert brief.requirements == [] and brief.dropped_quotes == 1


def test_model_schema_has_no_uuid_fields():
    assert "uuid" not in str(ModelBrief.model_json_schema()).lower()
