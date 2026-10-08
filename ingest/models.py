"""Source-independent opportunity model, field-compatible with the CommonGrants protocol."""

import hashlib
import json
import re
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Literal

from common_grants_sdk.schemas.pydantic import OpportunityBase
from pydantic import BaseModel, ConfigDict, Field

Kind = Literal["grant", "sbir", "sttr", "contract"]
Source = Literal["grants_gov", "sam_gov"]


class OppStatus(StrEnum):
    forecasted = "forecasted"
    open = "open"
    closed = "closed"
    custom = "custom"


class Money(BaseModel):
    model_config = ConfigDict(frozen=True)
    amount: Decimal
    currency: str = "USD"


class OppFunding(BaseModel):
    model_config = ConfigDict(frozen=True)
    total_amount_available: Money | None = None
    min_award_amount: Money | None = None
    max_award_amount: Money | None = None
    estimated_award_count: int | None = None
    details: str | None = None


class OppTimeline(BaseModel):
    model_config = ConfigDict(frozen=True)
    post_date: date | None = None
    close_date: date | None = None
    other_dates: dict[str, date] = Field(default_factory=dict)


class AttachmentRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    url: str
    file_name: str
    mime_type: str | None = None
    size_bytes: int | None = None


class Opportunity(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: Source
    source_id: str
    kind: Kind
    title: str
    status: OppStatus
    description: str
    agency: str
    source_url: str
    funding: OppFunding = Field(default_factory=OppFunding)
    key_dates: OppTimeline = Field(default_factory=OppTimeline)
    accepted_applicant_types: list[str] = Field(default_factory=list)
    naics: list[str] = Field(default_factory=list)
    assistance_listings: list[str] = Field(default_factory=list)
    attachments: list[AttachmentRef] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(default_factory=dict)
    raw_uri: str | None = Field(
        default=None, exclude=True
    )  # provenance; not part of content

    def content_hash(self) -> str:
        payload = json.dumps(
            self.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
        )
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_commongrants(
        self, *, record_id: uuid.UUID, created_at: datetime, last_modified_at: datetime
    ) -> OpportunityBase:
        """Export as the official CommonGrants OpportunityBase (validated by the SDK)."""

        def money(m: Money | None) -> dict[str, str] | None:
            return (
                None if m is None else {"amount": str(m.amount), "currency": m.currency}
            )

        def event(name: str, d: date | None) -> dict[str, str] | None:
            return (
                None
                if d is None
                else {"name": name, "eventType": "singleDate", "date": d.isoformat()}
            )

        def custom(name: str, value: Any) -> dict[str, Any]:
            kind = (
                "boolean"
                if isinstance(value, bool)
                else "integer"
                if isinstance(value, int)
                else "number"
                if isinstance(value, float)
                else "array"
                if isinstance(value, list)
                else "object"
                if isinstance(value, dict)
                else "string"
            )
            return {"name": name, "fieldType": kind, "value": value}

        f, k = self.funding, self.key_dates
        extra = {
            "sourceSystem": self.source,
            "sourceId": self.source_id,
            "kind": self.kind,
            "agency": self.agency,
            "naics": list(self.naics),
            "assistanceListings": list(self.assistance_listings),
            **self.custom_fields,
        }
        payload = {
            "id": str(record_id),
            "title": self.title,
            "status": {"value": self.status.value},
            "description": self.description or "(no description provided)",
            "funding": {
                "totalAmountAvailable": money(f.total_amount_available),
                "minAwardAmount": money(f.min_award_amount),
                "maxAwardAmount": money(f.max_award_amount),
                "estimatedAwardCount": f.estimated_award_count,
                "details": f.details,
            },
            "keyDates": {
                "postDate": event("Posted", k.post_date),
                "closeDate": event("Close date", k.close_date),
                "otherDates": {n: event(n, d) for n, d in k.other_dates.items()}
                or None,
            },
            "acceptedApplicantTypes": [
                to_cg_applicant_type(c) for c in self.accepted_applicant_types
            ],
            "source": self.source_url,
            "customFields": {
                n: custom(n, v) for n, v in extra.items() if v is not None
            },
            "createdAt": created_at.isoformat(),
            "lastModifiedAt": last_modified_at.isoformat(),
        }
        return OpportunityBase.model_validate(payload)


# Grants.gov applicant type codes -> CommonGrants ApplicantTypeOptions
_APPLICANT_TYPES = {
    "small_businesses": "for_profit_small_business",
    "for_profit_organizations_other_than_small_businesses": "for_profit_not_small_business",
    "individuals": "individual",
    "nonprofits_non_higher_education_with_501c3": "non_profit_with_501c3",
    "nonprofits_non_higher_education_without_501c3": "nonprofit_without_501c3",
    "public_and_state_institutions_of_higher_education": "higher_education_public",
    "private_institutions_of_higher_education": "higher_education_private",
    "state_governments": "government_state",
    "county_governments": "government_county",
    "city_or_township_governments": "government_municipal",
    "special_district_governments": "government_special_district",
    "independent_school_districts": "school_district_independent",
    "federally_recognized_native_american_tribal_governments": "government_tribal",
    "native_american_tribal_organizations": "organization_tribal_other",
    "unrestricted": "unrestricted",
}


def to_cg_applicant_type(code: str) -> dict[str, str]:
    value = _APPLICANT_TYPES.get(code)
    return {"value": value} if value else {"value": "custom", "customValue": code}


_STTR = re.compile(r"\bSTTR\b|technology transfer", re.IGNORECASE)
_SBIR = re.compile(r"\bSBIR\b|small business innovation research", re.IGNORECASE)


def infer_kind(*texts: str | None, default: Kind) -> Kind:
    joined = " ".join(t for t in texts if t)
    if _SBIR.search(joined):
        return "sbir"
    if _STTR.search(joined):
        return "sttr"
    return default


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    for parser in (
        lambda s: datetime.fromisoformat(s).date(),
        lambda s: datetime.strptime(s, "%m/%d/%Y").date(),
        lambda s: date.fromisoformat(
            s[:10]
        ),  # e.g. SAM bulk "2026-10-06 16:33:21.123-04"
    ):
        try:
            return parser(text)
        except ValueError:
            continue
    return None


def parse_money(value: Any) -> Money | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value).replace(",", "").replace("$", "").strip())
    except InvalidOperation:
        return None
    if amount <= 0:
        return None
    return Money(amount=amount)
