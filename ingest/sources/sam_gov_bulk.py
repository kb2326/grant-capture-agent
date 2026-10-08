"""SAM.gov Contract Opportunities daily public extract (no key, no quota, includes descriptions)."""

import csv
import time
from collections.abc import Iterator
from pathlib import Path

import httpx

from ingest.models import Opportunity, OppStatus, OppTimeline, infer_kind, parse_date
from ingest.raw import SAM_CSV_NAME, RawArchive
from ingest.sources.sam_gov import R_AND_D_NAICS

csv.field_size_limit(10_000_000)  # descriptions can be very long

SAM_BULK_URL = (
    "https://s3.amazonaws.com/falextracts/Contract%20Opportunities/datagov/"
    "ContractOpportunitiesFullCSV.csv"
)
BASE_TYPES = frozenset(
    {"Solicitation", "Presolicitation", "Combined Synopsis/Solicitation"}
)


def _get(r: dict[str, str], key: str) -> str:
    return (r.get(key) or "").strip()


def map_sam_csv_row(r: dict[str, str]) -> Opportunity:
    notice_id = _get(r, "NoticeId")
    agency_parts = [_get(r, k) for k in ("Department/Ind.Agency", "Sub-Tier", "Office")]
    return Opportunity(
        source="sam_gov",
        source_id=notice_id,
        kind=infer_kind(_get(r, "Title"), _get(r, "Sol#"), default="contract"),
        title=_get(r, "Title") or "(untitled)",
        status=OppStatus.open
        if _get(r, "Active").lower() == "yes"
        else OppStatus.closed,
        description=_get(r, "Description"),
        agency=" > ".join(p for p in agency_parts if p) or "Unknown agency",
        source_url=_get(r, "Link") or f"https://sam.gov/opp/{notice_id}/view",
        key_dates=OppTimeline(
            post_date=parse_date(_get(r, "PostedDate")),
            close_date=parse_date(_get(r, "ResponseDeadLine")),
        ),
        naics=[_get(r, "NaicsCode")] if _get(r, "NaicsCode") else [],
        custom_fields={
            "solicitation_number": _get(r, "Sol#") or None,
            "notice_type": _get(r, "Type") or None,
            "set_aside": _get(r, "SetASideCode") or None,
        },
    )


class SamBulkAdapter:
    name = "sam_gov"
    version = "sam_gov/1"

    def __init__(
        self,
        client: httpx.Client,
        *,
        cache_path: Path,
        url: str = SAM_BULK_URL,
        max_age_hours: float = 20,
        naics: tuple[str, ...] = R_AND_D_NAICS,
        archive: RawArchive | None = None,
    ) -> None:
        self.client, self.cache_path, self.url = client, cache_path, url
        self.max_age_s, self.naics = max_age_hours * 3600, frozenset(naics)
        self.archive = archive

    def _ensure_file(self) -> tuple[Path, bool]:
        """Return the cached extract and whether it was freshly downloaded."""
        path = self.cache_path
        if path.exists() and time.time() - path.stat().st_mtime < self.max_age_s:
            return path, False
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        with (
            self.client.stream("GET", self.url, timeout=600) as resp,
            tmp.open("wb") as fh,
        ):
            resp.raise_for_status()
            for chunk in resp.iter_bytes():
                fh.write(chunk)
        tmp.replace(path)
        return path, True

    def iter_opportunities(self, limit: int | None = None) -> Iterator[Opportunity]:
        yielded = 0
        path, downloaded = self._ensure_file()
        csv_key = None
        if self.archive:
            csv_key = self.archive.key(SAM_CSV_NAME)
            if downloaded or not self.archive.store.exists(csv_key):
                self.archive.put_bytes(SAM_CSV_NAME, path.read_bytes())
        # The extract is not strictly UTF-8; decode leniently so one bad byte can't stop the run.
        with path.open(encoding="utf-8", errors="replace", newline="") as fh:
            for row in csv.DictReader(fh):
                if (
                    _get(row, "NaicsCode") not in self.naics
                    or _get(row, "BaseType") not in BASE_TYPES
                ):
                    continue
                o = map_sam_csv_row(row)
                yield (
                    o.model_copy(update={"raw_uri": f"{csv_key}#{o.source_id}"})
                    if csv_key
                    else o
                )
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
