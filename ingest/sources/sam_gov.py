"""SAM.gov Get Opportunities API v2. Public keys allow ~10 requests/day, so every call is budgeted."""

import json
import logging
from collections.abc import Iterator
from datetime import date, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import urlparse

import httpx

from ingest.http import RetryableHTTPError, request_json
from ingest.models import (
    AttachmentRef,
    Opportunity,
    OppStatus,
    OppTimeline,
    infer_kind,
    parse_date,
)

if TYPE_CHECKING:
    from ingest.raw import RawArchive
    from ingest.storage import BlobStore

log = logging.getLogger(__name__)

SAM_URL = "https://api.sam.gov/opportunities/v2/search"
R_AND_D_NAICS = ("541713", "541714", "541715")
NOTICE_TYPES = ("o", "p", "k")


def _file_name(url: str) -> str:
    parts = [p for p in urlparse(url).path.split("/") if p]
    if parts and parts[-1] == "download" and len(parts) >= 2:
        return parts[-2]
    return parts[-1] if parts else "attachment"


def map_sam_gov(r: dict[str, Any]) -> Opportunity:
    links = r.get("resourceLinks") or []
    return Opportunity(
        source="sam_gov_api",  # on-demand lookups; never overwrites the bulk-extract rows
        source_id=str(r["noticeId"]),
        kind=infer_kind(
            r.get("title"), r.get("solicitationNumber"), default="contract"
        ),
        title=r.get("title") or "(untitled)",
        status=OppStatus.open
        if (r.get("active") or "").lower() == "yes"
        else OppStatus.closed,
        description="",  # SAM returns a URL that costs one request per notice; fetched on demand in M1
        agency=" > ".join(
            p for p in (r.get("fullParentPathName") or "Unknown agency").split(".") if p
        ),
        source_url=r.get("uiLink") or f"https://sam.gov/opp/{r['noticeId']}/view",
        key_dates=OppTimeline(
            post_date=parse_date(r.get("postedDate")),
            close_date=parse_date(r.get("responseDeadLine")),
        ),
        naics=[r["naicsCode"]] if r.get("naicsCode") else [],
        attachments=[AttachmentRef(url=u, file_name=_file_name(u)) for u in links],
        custom_fields={
            "solicitation_number": r.get("solicitationNumber"),
            "notice_type": r.get("type"),
            "set_aside": r.get("typeOfSetAside"),
            "set_aside_description": r.get("typeOfSetAsideDescription"),
            "classification_code": r.get("classificationCode"),
            "description_url": r.get("description"),
        },
    )


class SamQuota:
    """Per-day SAM.gov API request count, persisted so separate runs share one budget."""

    def __init__(self, store: "BlobStore", day: date) -> None:
        self.store = store
        self.key = f"raw/api/sam_gov_api/{day:%Y-%m-%d}/_quota.json"

    def used(self) -> int:
        if not self.store.exists(self.key):
            return 0
        return int(json.loads(self.store.get(self.key)).get("requests", 0))

    def record(self, requests: int) -> None:
        self.store.put(self.key, json.dumps({"requests": requests}).encode("utf-8"))


def _describe(exc: Exception) -> str:
    """Error summary without the URL query string (it carries the API key)."""
    if isinstance(exc, httpx.HTTPStatusError):
        return f"HTTP {exc.response.status_code}"
    return type(exc).__name__


class SamGovAdapter:
    name = "sam_gov_api"
    version = "sam_gov_api/1"

    def __init__(
        self,
        client: httpx.Client,
        api_key: str,
        *,
        request_budget: int,
        today: date | None = None,
        page_size: int = 1000,
        archive: "RawArchive | None" = None,
        quota: SamQuota | None = None,
    ) -> None:
        self.client, self.api_key, self.page_size = client, api_key, page_size
        self.request_budget, self.today = request_budget, today or date.today()
        self.quota = quota
        self.requests_made = quota.used() if quota else 0
        self.budget_exhausted = False
        self.archive = archive

    def _search(self, ptype: str, naics: str, offset: int) -> dict[str, Any] | None:
        if self.requests_made >= self.request_budget:
            if not self.budget_exhausted:
                log.warning(
                    "SAM.gov request budget (%d) reached; stopping", self.request_budget
                )
            self.budget_exhausted = True
            return None
        self.requests_made += 1  # every HTTP attempt counts: there are no retries below
        if self.quota:
            self.quota.record(self.requests_made)
        params = {
            "api_key": self.api_key,
            "ptype": ptype,
            "ncode": naics,
            "postedFrom": (self.today - timedelta(days=364)).strftime("%m/%d/%Y"),
            "postedTo": self.today.strftime("%m/%d/%Y"),
            "limit": str(self.page_size),
            "offset": str(offset),
        }
        try:
            payload = request_json(
                self.client, "GET", SAM_URL, params=params, max_attempts=1
            )
        except (httpx.HTTPError, RetryableHTTPError) as exc:
            log.warning(
                "SAM.gov request failed (%s); stopping to protect the daily quota",
                _describe(exc),
            )
            self.budget_exhausted = True
            return None
        if self.archive:
            self.archive.put_json(f"search-{ptype}-{naics}-{offset}", payload)
        return payload

    def fetch_notice(
        self, notice_id: str, posted_at: date | None = None
    ) -> dict | None:
        """One notice by ID (one budgeted request). None if the budget is spent or the call fails.

        The API requires a posted-date range; searching a day either side of the notice's own posted
        date finds notices that are older than a year (long-running BAAs)."""
        if self.budget_exhausted or self.requests_made >= self.request_budget:
            self.budget_exhausted = True
            return None
        self.requests_made += 1
        if self.quota:
            self.quota.record(self.requests_made)
        params = {
            "api_key": self.api_key,
            "noticeid": notice_id,
            "limit": "1",
            "offset": "0",
            "postedFrom": (
                posted_at - timedelta(days=1)
                if posted_at
                else self.today - timedelta(days=364)
            ).strftime("%m/%d/%Y"),
            "postedTo": (
                posted_at + timedelta(days=1) if posted_at else self.today
            ).strftime("%m/%d/%Y"),
        }
        try:
            payload = request_json(
                self.client, "GET", SAM_URL, params=params, max_attempts=1
            )
        except (httpx.HTTPError, RetryableHTTPError) as exc:
            log.warning("SAM.gov notice lookup failed (%s)", _describe(exc))
            self.budget_exhausted = True
            return None
        if self.archive:
            self.archive.put_json(f"notice-{notice_id}", payload)
        records = payload.get("opportunitiesData") or []
        return records[0] if records else None

    def iter_opportunities(self, limit: int | None = None) -> Iterator[Opportunity]:
        seen: set[str] = set()
        for ptype in NOTICE_TYPES:
            for naics in R_AND_D_NAICS:
                offset = 0
                while True:
                    payload = self._search(ptype, naics, offset)
                    if payload is None:
                        return
                    records = payload.get("opportunitiesData") or []
                    for r in records:
                        if r.get("noticeId") in seen:
                            continue
                        seen.add(r["noticeId"])
                        yield map_sam_gov(r)
                        if limit is not None and len(seen) >= limit:
                            return
                    if (
                        offset + len(records) >= int(payload.get("totalRecords") or 0)
                        or not records
                    ):
                        break
                    offset += len(records)
