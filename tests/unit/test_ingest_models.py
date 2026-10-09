import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from common_grants_sdk.schemas.pydantic import OpportunityBase

from ingest.models import (
    AttachmentRef,
    Money,
    Opportunity,
    OppStatus,
    OppTimeline,
    infer_kind,
    parse_date,
    parse_money,
)


def _opp(**kw):
    base = dict(
        source="grants_gov",
        source_id="abc",
        kind="grant",
        title="Grid storage R&D",
        status=OppStatus.open,
        description="desc",
        agency="DOE",
        source_url="https://x/abc",
    )
    base.update(kw)
    return Opportunity(**base)


def test_content_hash_is_stable_and_sensitive():
    a, b = _opp(), _opp()
    assert a.content_hash() == b.content_hash()
    assert len(a.content_hash()) == 64
    assert _opp(title="Changed").content_hash() != a.content_hash()
    assert (
        _opp(
            attachments=[AttachmentRef(url="https://f/1.pdf", file_name="1.pdf")]
        ).content_hash()
        != a.content_hash()
    )


def test_commongrants_export_validates_against_official_sdk():
    o = _opp(
        key_dates=OppTimeline(post_date=date(2026, 9, 1), close_date=date(2026, 11, 3)),
        accepted_applicant_types=["small_businesses", "weird_new_code"],
    )
    rid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    now = datetime(2026, 10, 7, tzinfo=UTC)
    cg = o.to_commongrants(record_id=rid, created_at=now, last_modified_at=now)
    assert isinstance(cg, OpportunityBase)
    d = cg.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert d["id"] == str(rid) and d["title"] == "Grid storage R&D"
    assert d["status"]["value"] == "open"
    assert d["keyDates"]["closeDate"]["eventType"] == "singleDate"
    assert d["keyDates"]["closeDate"]["date"] == "2026-11-03"
    assert d["acceptedApplicantTypes"][0]["value"] == "for_profit_small_business"
    assert d["acceptedApplicantTypes"][1] == {
        "value": "custom",
        "customValue": "weird_new_code",
    }
    assert d["customFields"]["sourceId"]["value"] == "abc"
    assert d["source"] == "https://x/abc"


def test_empty_description_still_exports():
    now = datetime(2026, 10, 7, tzinfo=UTC)
    cg = _opp(description="").to_commongrants(
        record_id=uuid.uuid4(), created_at=now, last_modified_at=now
    )
    assert cg.description == "(no description provided)"


def test_infer_kind():
    assert infer_kind("DOE SBIR/STTR FY27 Phase I Release 1", default="grant") == "sbir"
    assert (
        infer_kind("Small Business Technology Transfer (STTR) Phase I", default="grant")
        == "sttr"
    )
    assert (
        infer_kind("Advanced Battery Materials", None, default="contract") == "contract"
    )


def test_parse_helpers_tolerate_messy_values():
    assert parse_date("2026-11-03") == date(2026, 11, 3)
    assert parse_date("2026-11-03T17:00:00-04:00") == date(2026, 11, 3)
    assert parse_date("11/03/2026") == date(2026, 11, 3)
    assert parse_date("2026-10-06 16:33:21.123-04") == date(
        2026, 10, 6
    )  # SAM bulk CSV format
    assert (
        parse_date(None) is None
        and parse_date("") is None
        and parse_date("TBD") is None
    )
    assert parse_money(150000) == Money(amount=Decimal("150000"))
    assert parse_money("1,250,000.50") == Money(amount=Decimal("1250000.50"))
    assert (
        parse_money(None) is None
        and parse_money("N/A") is None
        and parse_money(0) is None
    )


def test_raw_uri_is_provenance_not_content():
    with_uri = _opp(raw_uri="raw/api/x/2026-10-07/a.json")
    assert with_uri.raw_uri == "raw/api/x/2026-10-07/a.json"
    assert _opp().content_hash() == with_uri.content_hash()
