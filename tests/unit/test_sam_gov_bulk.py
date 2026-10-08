import os
import time
from datetime import date
from pathlib import Path

import httpx
import respx

from ingest.http import build_client
from ingest.models import OppStatus
from ingest.sources.sam_gov_bulk import SAM_BULK_URL, SamBulkAdapter, map_sam_csv_row

SAMPLE = Path("tests/fixtures/sam_gov/bulk_sample.csv").read_bytes()


def test_map_row():
    row = {
        "NoticeId": "n-101",
        "Title": "SBIR Phase I: Grid-Forming Inverter Controls",
        "Sol#": "W911",
        "Department/Ind.Agency": "DEPT OF DEFENSE",
        "Sub-Tier": "DEPT OF THE ARMY",
        "Office": "ARL",
        "PostedDate": "2026-10-01 09:12:00.000-04",
        "Type": "Solicitation",
        "BaseType": "Solicitation",
        "SetASideCode": "SBA",
        "ResponseDeadLine": "2026-11-20T17:00:00-05:00",
        "NaicsCode": "541715",
        "Active": "Yes",
        "Link": "https://sam.gov/opp/n-101/view",
        "Description": "Seeking research.",
    }
    o = map_sam_csv_row(row)
    assert o.source == "sam_gov" and o.kind == "sbir" and o.status is OppStatus.open
    assert o.agency == "DEPT OF DEFENSE > DEPT OF THE ARMY > ARL"
    assert o.key_dates.post_date == date(
        2026, 10, 1
    ) and o.key_dates.close_date == date(2026, 11, 20)
    assert o.description == "Seeking research." and o.attachments == []
    assert o.custom_fields["set_aside"] == "SBA"


@respx.mock
def test_filters_to_rd_naics_and_notice_types(tmp_path: Path):
    respx.get(SAM_BULK_URL).mock(return_value=httpx.Response(200, content=SAMPLE))
    with build_client() as c:
        opps = list(
            SamBulkAdapter(c, cache_path=tmp_path / "sam.csv").iter_opportunities()
        )
    # n-102: wrong NAICS; n-103: award notice; n-104 kept although inactive (status closed)
    assert [o.source_id for o in opps] == ["n-101", "n-104"]
    assert opps[1].status is OppStatus.closed


@respx.mock
def test_fresh_cache_skips_download_and_stale_cache_refreshes(tmp_path: Path):
    cache = tmp_path / "sam.csv"
    cache.write_bytes(SAMPLE)
    route = respx.get(SAM_BULK_URL).mock(
        return_value=httpx.Response(200, content=SAMPLE)
    )
    with build_client() as c:
        assert len(list(SamBulkAdapter(c, cache_path=cache).iter_opportunities())) == 2
    assert route.call_count == 0
    old = time.time() - 30 * 3600
    os.utime(cache, (old, old))
    with build_client() as c:
        list(SamBulkAdapter(c, cache_path=cache).iter_opportunities())
    assert route.call_count == 1
