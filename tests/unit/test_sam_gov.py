import json
from datetime import date
from pathlib import Path

import httpx
import respx

from ingest.http import build_client
from ingest.models import OppStatus
from ingest.sources.sam_gov import SAM_URL, SamGovAdapter, map_sam_gov

FIX = json.loads(
    Path("tests/fixtures/sam_gov/search_o_541715.json").read_text(encoding="utf-8")
)


def test_map_records_including_nulls_and_timezones():
    a = map_sam_gov(FIX["opportunitiesData"][0])
    assert a.source == "sam_gov" and a.source_id == "n-001" and a.kind == "sbir"
    assert a.status is OppStatus.open
    assert a.key_dates.close_date == date(2026, 11, 15)
    assert a.agency == "DEPT OF DEFENSE > DEPT OF THE ARMY > ARL"
    assert a.naics == ["541715"]
    assert a.attachments[0].file_name == "f1"
    assert a.custom_fields["set_aside"] == "SBA"
    assert a.custom_fields["description_url"].endswith("noticeid=n-001")
    b = map_sam_gov(FIX["opportunitiesData"][1])
    assert (
        b.kind == "contract" and b.key_dates.close_date is None and b.attachments == []
    )
    assert b.description == ""


@respx.mock
def test_budget_is_never_exceeded():
    route = respx.get(SAM_URL).mock(return_value=httpx.Response(200, json=FIX))
    with build_client() as c:
        adapter = SamGovAdapter(c, "key", request_budget=2, today=date(2026, 10, 7))
        opps = list(adapter.iter_opportunities())
    assert route.call_count == 2
    assert adapter.requests_made == 2 and adapter.budget_exhausted
    assert len({o.source_id for o in opps}) == len(
        opps
    )  # deduplicated across query combos


@respx.mock
def test_query_parameters():
    route = respx.get(SAM_URL).mock(
        return_value=httpx.Response(
            200, json={"totalRecords": 0, "opportunitiesData": []}
        )
    )
    with build_client() as c:
        list(
            SamGovAdapter(
                c, "key", request_budget=1, today=date(2026, 10, 7)
            ).iter_opportunities()
        )
    params = dict(route.calls[0].request.url.params)
    assert (
        params["api_key"] == "key"
        and params["ptype"] == "o"
        and params["ncode"] == "541713"
    )
    assert params["postedFrom"] == "10/08/2025" and params["postedTo"] == "10/07/2026"
    assert params["limit"] == "1000" and params["offset"] == "0"
