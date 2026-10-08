"""Grants.gov via the Simpler Grants API (https://api.simpler.grants.gov)."""

import time
from collections.abc import Iterator
from typing import TYPE_CHECKING, Any

import httpx

from ingest.http import request_json
from ingest.models import (
    AttachmentRef,
    OppFunding,
    Opportunity,
    OppStatus,
    OppTimeline,
    infer_kind,
    parse_date,
    parse_money,
)

if TYPE_CHECKING:
    from ingest.raw import RawArchive

GRANTS_BASE = "https://api.simpler.grants.gov"
_STATUS = {
    "posted": OppStatus.open,
    "forecasted": OppStatus.forecasted,
    "closed": OppStatus.closed,
    "archived": OppStatus.closed,
}


def map_grants_gov(d: dict[str, Any]) -> Opportunity:
    s = d.get("summary") or {}
    forecast = bool(s.get("is_forecast"))
    names = [n for n in (d.get("top_level_agency_name"), d.get("agency_name")) if n]
    agency = " / ".join(dict.fromkeys(names)) or "Unknown agency"
    estimated = s.get("expected_number_of_awards")
    return Opportunity(
        source="grants_gov",
        source_id=str(d["opportunity_id"]),
        kind=infer_kind(
            d.get("opportunity_title"), d.get("opportunity_number"), default="grant"
        ),
        title=d.get("opportunity_title") or "(untitled)",
        status=_STATUS.get(d.get("opportunity_status") or "", OppStatus.custom),
        description=s.get("summary_description") or "",
        agency=agency,
        source_url=f"https://simpler.grants.gov/opportunity/{d['opportunity_id']}",
        funding=OppFunding(
            total_amount_available=parse_money(
                s.get("estimated_total_program_funding")
            ),
            min_award_amount=parse_money(s.get("award_floor")),
            max_award_amount=parse_money(s.get("award_ceiling")),
            estimated_award_count=estimated if isinstance(estimated, int) else None,
        ),
        key_dates=OppTimeline(
            post_date=parse_date(
                s.get("forecasted_post_date") if forecast else s.get("post_date")
            ),
            close_date=parse_date(
                s.get("forecasted_close_date") if forecast else s.get("close_date")
            ),
        ),
        accepted_applicant_types=list(s.get("applicant_types") or []),
        assistance_listings=[
            a["assistance_listing_number"]
            for a in (d.get("opportunity_assistance_listings") or [])
            if a.get("assistance_listing_number")
        ],
        attachments=[
            AttachmentRef(
                url=a["download_path"],
                file_name=a.get("file_name") or "",
                mime_type=a.get("mime_type"),
                size_bytes=a.get("file_size_bytes"),
            )
            for a in (d.get("attachments") or [])
            if a.get("download_path")
        ],
        custom_fields={
            "opportunity_number": d.get("opportunity_number"),
            "agency_code": d.get("agency_code"),
            "funding_instruments": list(s.get("funding_instruments") or []),
            "is_cost_sharing": s.get("is_cost_sharing"),
            "applicant_eligibility_description": s.get(
                "applicant_eligibility_description"
            ),
        },
    )


class GrantsGovAdapter:
    name = "grants_gov"
    version = "grants_gov/1"

    def __init__(
        self,
        client: httpx.Client,
        api_key: str,
        page_size: int = 100,
        min_interval_s: float = 1.1,
        sleep=time.sleep,
        clock=time.monotonic,
        archive: "RawArchive | None" = None,
    ) -> None:
        self.client, self.page_size = client, page_size
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        self.min_interval_s, self._sleep, self._clock = min_interval_s, sleep, clock
        self._last: float | None = None
        self.archive = archive

    def _call(self, method: str, url: str, **kwargs):
        # Simpler Grants allows 60 requests/minute per key; stay just under it.
        if self._last is not None:
            wait = self.min_interval_s - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()
        return request_json(self.client, method, url, headers=self.headers, **kwargs)

    def iter_opportunities(self, limit: int | None = None) -> Iterator[Opportunity]:
        page, yielded = 1, 0
        while True:
            body = {
                "filters": {"opportunity_status": {"one_of": ["posted", "forecasted"]}},
                "pagination": {
                    "page_offset": page,
                    "page_size": self.page_size,
                    "sort_order": [
                        {"order_by": "post_date", "sort_direction": "descending"}
                    ],
                },
            }
            payload = self._call(
                "POST", f"{GRANTS_BASE}/v1/opportunities/search", json=body
            )
            if self.archive:
                self.archive.put_json(f"search-page-{page:04d}", payload)
            for item in payload.get("data") or []:
                detail = self._call(
                    "GET", f"{GRANTS_BASE}/v1/opportunities/{item['opportunity_id']}"
                )
                raw_key = (
                    self.archive.put_json(f"detail-{item['opportunity_id']}", detail)
                    if self.archive
                    else None
                )
                yield map_grants_gov(detail["data"]).model_copy(
                    update={"raw_uri": raw_key}
                )
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            if page >= (payload.get("pagination_info") or {}).get("total_pages", page):
                return
            page += 1
