import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.analyze.llm import LlmResult
from app.analyze.service import NoDocuments, analyze
from app.config import Settings
from app.contracts import ModelBrief
from db.models import (
    CompanyRow,
    DocumentRow,
    EligibilityVerdictRow,
    OpportunityRow,
    SolicitationBriefRow,
)
from ingest.parsing import parse_documents
from ingest.storage import LocalBlobStore, read_uri

pytestmark = pytest.mark.db

PAGE1 = "Eligible applicants: Only nonprofit organizations may apply for this funding opportunity."
PAGE2 = (
    "Proposals shall not exceed fifteen pages including all attachments and appendices."
)


class FakeModel:
    model_id = "fake"

    def extract(self, parts, instruction):
        return LlmResult(
            ModelBrief.model_validate(
                {
                    "eligibility": [
                        {
                            "category": "entity_type",
                            "citation": {
                                "doc": 1,
                                "page": 1,
                                "quote": "Only nonprofit organizations may apply",
                            },
                            "constraint": {"allowed": ["nonprofit"]},
                        }
                    ],
                    "requirements": [
                        {
                            "text": "15 page limit",
                            "citation": {
                                "doc": 1,
                                "page": 2,
                                "quote": "shall not exceed fifteen pages",
                            },
                        },
                        {
                            "text": "invented",
                            "citation": {
                                "doc": 1,
                                "page": 2,
                                "quote": "must include a video pitch",
                            },
                        },
                    ],
                    "evaluation_criteria": [],
                    "required_sections": [],
                    "deadlines": [],
                }
            ),
            900,
            120,
            0.2,
        )


def _seed(db_session, tmp_path: Path, with_doc: bool = True) -> uuid.UUID:
    profile = json.loads(Path("data/company/profile.json").read_text(encoding="utf-8"))
    db_session.add(CompanyRow(name=profile["name"], profile=profile))
    opp = OpportunityRow(
        id=uuid.uuid4(),
        source="grants_gov",
        source_id="a1",
        kind="grant",
        title="t",
        agency="a",
        summary="",
        url="u",
        status="open",
        naics=[],
        assistance_listings=[],
        eligibility_codes=[],
        raw={},
        content_hash="h",
    )
    db_session.add(opp)
    db_session.flush()
    if with_doc:
        html = (
            f"<h2>Eligibility</h2><p>{PAGE1}</p><h2>Format</h2><p>{PAGE2}</p>".encode()
        )
        uri = LocalBlobStore(tmp_path).put("raw/grants_gov/a1/n.html", html)
        db_session.add(
            DocumentRow(
                opportunity_id=opp.id,
                corpus="solicitation",
                gcs_uri=uri,
                mime="text/html",
                title="n.html",
                sha256="s",
                parse_status="pending",
            )
        )
    db_session.commit()
    parse_documents(db_session, read_uri)
    return opp.id


def test_analyze_verifies_quotes_decides_and_persists(db_session, tmp_path: Path):
    opp_id = _seed(db_session, tmp_path)
    result = analyze(
        db_session,
        opp_id,
        model=FakeModel(),
        read=read_uri,
        settings=Settings(_env_file=None),
    )
    assert result.verdict.status == "INELIGIBLE"
    assert len(result.brief.requirements) == 1 and result.brief.dropped_quotes == 1
    stored = db_session.scalars(select(SolicitationBriefRow)).one()
    assert stored.prompt_version == "brief_v1" and stored.brief["variant"] == "B0"
    assert (
        db_session.scalars(select(EligibilityVerdictRow)).one().verdict == "INELIGIBLE"
    )


def test_no_documents_is_a_clear_result(db_session, tmp_path: Path):
    opp_id = _seed(db_session, tmp_path, with_doc=False)
    with pytest.raises(NoDocuments):
        analyze(
            db_session,
            opp_id,
            model=FakeModel(),
            read=read_uri,
            settings=Settings(_env_file=None),
        )
