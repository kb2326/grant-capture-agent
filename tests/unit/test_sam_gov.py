import json
import logging
from datetime import date
from pathlib import Path

import httpx
import respx

from ingest.http import build_client
from ingest.logging_setup import configure_logging
from ingest.models import OppStatus
from ingest.sources.sam_gov import SAM_URL, SamGovAdapter, SamQuota, map_sam_gov
from ingest.storage import LocalBlobStore

FIX = json.loads(
    Path("tests/fixtures/sam_gov/search_o_541715.json").read_text(encoding="utf-8")
)


def test_map_records_including_nulls_and_timezones():
    a = map_sam_gov(FIX["opportunitiesData"][0])
    assert a.source == "sam_gov_api" and a.source_id == "n-001" and a.kind == "sbir"
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


@respx.mock
def test_api_key_never_logged_and_errors_stop_cleanly(caplog):
    configure_logging()
    respx.get(SAM_URL).mock(
        return_value=httpx.Response(403, json={"error": "forbidden"})
    )
    with caplog.at_level(logging.DEBUG), build_client() as c:
        adapter = SamGovAdapter(
            c, "SECRETKEY123", request_budget=3, today=date(2026, 10, 7)
        )
        opps = list(adapter.iter_opportunities())  # must not raise
    assert opps == [] and adapter.budget_exhausted
    assert "SECRETKEY123" not in caplog.text


@respx.mock
def test_every_http_attempt_counts_and_server_errors_stop_cleanly():
    route = respx.get(SAM_URL).mock(return_value=httpx.Response(503))
    with build_client() as c:
        adapter = SamGovAdapter(c, "k", request_budget=5, today=date(2026, 10, 7))
        assert list(adapter.iter_opportunities()) == []
    assert (
        route.call_count == 1
        and adapter.requests_made == 1
        and adapter.budget_exhausted
    )


@respx.mock
def test_quota_is_shared_across_runs_on_the_same_day(tmp_path):
    route = respx.get(SAM_URL).mock(return_value=httpx.Response(200, json=FIX))
    store, day = LocalBlobStore(tmp_path), date(2026, 10, 7)
    with build_client() as c:
        first = SamGovAdapter(
            c, "k", request_budget=3, today=day, quota=SamQuota(store, day)
        )
        list(first.iter_opportunities())
        second = SamGovAdapter(
            c, "k", request_budget=3, today=day, quota=SamQuota(store, day)
        )
        assert list(second.iter_opportunities()) == []
    assert route.call_count == 3 and second.budget_exhausted


@respx.mock
def test_fetch_notice_uses_noticeid_and_counts_quota(tmp_path):
    route = respx.get(SAM_URL).mock(
        return_value=httpx.Response(
            200,
            json={
                "totalRecords": 1,
                "opportunitiesData": [FIX["opportunitiesData"][0]],
            },
        )
    )
    store, day = LocalBlobStore(tmp_path), date(2026, 10, 9)
    with build_client() as c:
        adapter = SamGovAdapter(
            c, "k", request_budget=2, today=day, quota=SamQuota(store, day)
        )
        rec = adapter.fetch_notice("n-001")
    assert rec["noticeId"] == "n-001" and adapter.requests_made == 1
    assert dict(route.calls[0].request.url.params)["noticeid"] == "n-001"


@respx.mock
def test_fetch_notice_stops_after_first_failure_to_protect_quota(tmp_path):
    route = respx.get(SAM_URL).mock(return_value=httpx.Response(500))
    store, day = LocalBlobStore(tmp_path), date(2026, 10, 9)
    with build_client() as c:
        adapter = SamGovAdapter(
            c, "k", request_budget=8, today=day, quota=SamQuota(store, day)
        )
        assert adapter.fetch_notice("n-001") is None
        assert adapter.fetch_notice("n-002") is None
    assert route.call_count == 1 and adapter.requests_made == 1


@respx.mock
def test_fetch_notice_searches_the_window_around_its_posted_date(tmp_path):
    route = respx.get(SAM_URL).mock(
        return_value=httpx.Response(
            200, json={"totalRecords": 0, "opportunitiesData": []}
        )
    )
    store, day = LocalBlobStore(tmp_path), date(2026, 10, 9)
    with build_client() as c:
        adapter = SamGovAdapter(
            c, "k", request_budget=2, today=day, quota=SamQuota(store, day)
        )
        adapter.fetch_notice("old-1", posted_at=date(2023, 1, 5))
    params = dict(route.calls[0].request.url.params)
    assert params["postedFrom"] == "01/04/2023" and params["postedTo"] == "01/06/2023"
