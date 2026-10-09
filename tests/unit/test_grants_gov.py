import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import respx

from ingest.http import build_client
from ingest.models import OppStatus
from ingest.sources.grants_gov import GRANTS_BASE, GrantsGovAdapter, map_grants_gov

FIX = Path("tests/fixtures/grants_gov")


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_map_full_record():
    o = map_grants_gov(load("detail_full.json")["data"])
    assert (
        o.source == "grants_gov"
        and o.source_id == "11111111-1111-1111-1111-111111111111"
    )
    assert o.kind == "sbir" and o.status is OppStatus.open
    assert o.agency == "Department of Energy / Office of Science"
    assert o.key_dates.post_date == date(
        2026, 9, 15
    ) and o.key_dates.close_date == date(2026, 11, 3)
    assert o.funding.max_award_amount.amount == Decimal("200000")
    assert o.funding.estimated_award_count == 150
    assert o.accepted_applicant_types == ["small_businesses"]
    assert o.assistance_listings == ["81.049"]
    assert [a.file_name for a in o.attachments] == ["DE-FOA-0003500.pdf", "budget.xlsx"]
    assert o.custom_fields["opportunity_number"] == "DE-FOA-0003500"
    assert (
        "small business concerns"
        in o.custom_fields["applicant_eligibility_description"]
    )
    assert (
        o.source_url
        == "https://simpler.grants.gov/opportunity/11111111-1111-1111-1111-111111111111"
    )


def test_map_sparse_forecast_record():
    o = map_grants_gov(load("detail_sparse.json")["data"])
    assert o.status is OppStatus.forecasted
    assert o.kind == "grant"
    assert o.agency == "Department of Energy"
    assert o.key_dates.post_date == date(2026, 12, 1) and o.key_dates.close_date is None
    assert o.description == "" and o.attachments == [] and o.assistance_listings == []
    assert o.funding.max_award_amount is None


@respx.mock
def test_adapter_pages_and_fetches_details():
    search = respx.post(f"{GRANTS_BASE}/v1/opportunities/search").mock(
        return_value=httpx.Response(200, json=load("search_page1.json"))
    )
    respx.get(
        f"{GRANTS_BASE}/v1/opportunities/11111111-1111-1111-1111-111111111111"
    ).mock(return_value=httpx.Response(200, json=load("detail_full.json")))
    respx.get(
        f"{GRANTS_BASE}/v1/opportunities/22222222-2222-2222-2222-222222222222"
    ).mock(return_value=httpx.Response(200, json=load("detail_sparse.json")))
    with build_client() as c:
        opps = list(
            GrantsGovAdapter(
                c, api_key="k", page_size=2, min_interval_s=0
            ).iter_opportunities()
        )
    assert [o.source_id[:4] for o in opps] == ["1111", "2222"]
    sent = json.loads(search.calls[0].request.content)
    assert sent["filters"]["opportunity_status"]["one_of"] == ["posted", "forecasted"]
    assert search.calls[0].request.headers["X-API-Key"] == "k"


@respx.mock
def test_adapter_respects_limit():
    respx.post(f"{GRANTS_BASE}/v1/opportunities/search").mock(
        return_value=httpx.Response(200, json=load("search_page1.json"))
    )
    detail = respx.get(url__startswith=f"{GRANTS_BASE}/v1/opportunities/").mock(
        return_value=httpx.Response(200, json=load("detail_full.json"))
    )
    with build_client() as c:
        opps = list(
            GrantsGovAdapter(c, api_key="k", min_interval_s=0).iter_opportunities(
                limit=1
            )
        )
    assert len(opps) == 1 and detail.call_count == 1


@respx.mock
def test_adapter_throttles_to_rate_limit():
    respx.post(f"{GRANTS_BASE}/v1/opportunities/search").mock(
        return_value=httpx.Response(200, json=load("search_page1.json"))
    )
    respx.get(url__startswith=f"{GRANTS_BASE}/v1/opportunities/").mock(
        return_value=httpx.Response(200, json=load("detail_full.json"))
    )
    sleeps: list[float] = []
    with build_client() as c:
        adapter = GrantsGovAdapter(
            c,
            api_key="k",
            page_size=2,
            min_interval_s=1.1,
            sleep=sleeps.append,
            clock=lambda: 0.0,
        )
        list(adapter.iter_opportunities())
    assert sleeps == [1.1, 1.1]  # 3 requests (1 search + 2 details) → 2 waits


@respx.mock
def test_one_failed_detail_does_not_stop_the_adapter():
    respx.post(f"{GRANTS_BASE}/v1/opportunities/search").mock(
        return_value=httpx.Response(200, json=load("search_page1.json"))
    )
    respx.get(
        f"{GRANTS_BASE}/v1/opportunities/11111111-1111-1111-1111-111111111111"
    ).mock(return_value=httpx.Response(404))
    respx.get(
        f"{GRANTS_BASE}/v1/opportunities/22222222-2222-2222-2222-222222222222"
    ).mock(return_value=httpx.Response(200, json=load("detail_sparse.json")))
    with build_client() as c:
        adapter = GrantsGovAdapter(c, "k", page_size=2, min_interval_s=0)
        opps = list(adapter.iter_opportunities())
    assert [o.source_id[:4] for o in opps] == ["2222"]
    assert len(adapter.errors) == 1 and "11111111" in adapter.errors[0]
