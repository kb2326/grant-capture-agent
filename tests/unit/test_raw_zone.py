import json
from datetime import date
from pathlib import Path

import httpx
import respx

from ingest.http import build_client
from ingest.raw import RawArchive, replay_grants_gov, replay_sam_bulk
from ingest.sources.grants_gov import GRANTS_BASE, GrantsGovAdapter
from ingest.sources.sam_gov_bulk import SAM_BULK_URL, SamBulkAdapter
from ingest.storage import LocalBlobStore

FIX = Path("tests/fixtures/grants_gov")
DAY = date(2026, 10, 7)


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_archive_round_trip_and_listing(tmp_path: Path):
    archive = RawArchive(LocalBlobStore(tmp_path), "grants_gov", DAY)
    key = archive.put_json("detail-../../evil", {"a": 1})
    assert key == "raw/api/grants_gov/2026-10-07/detail-_evil.json"
    archive.put_json("search-page-0001", {"b": 2})
    assert [k for k, _ in archive.iter_json("detail-")] == [key]
    assert len(list(archive.iter_json())) == 2


@respx.mock
def test_grants_adapter_archives_raw_and_sets_provenance(tmp_path: Path):
    respx.post(f"{GRANTS_BASE}/v1/opportunities/search").mock(
        return_value=httpx.Response(200, json=load("search_page1.json"))
    )
    respx.get(
        f"{GRANTS_BASE}/v1/opportunities/11111111-1111-1111-1111-111111111111"
    ).mock(return_value=httpx.Response(200, json=load("detail_full.json")))
    respx.get(
        f"{GRANTS_BASE}/v1/opportunities/22222222-2222-2222-2222-222222222222"
    ).mock(return_value=httpx.Response(200, json=load("detail_sparse.json")))
    archive = RawArchive(LocalBlobStore(tmp_path), "grants_gov", DAY)
    with build_client() as c:
        live = list(
            GrantsGovAdapter(
                c, "k", page_size=2, min_interval_s=0, archive=archive
            ).iter_opportunities()
        )
    assert (
        live[0].raw_uri
        == "raw/api/grants_gov/2026-10-07/detail-11111111-1111-1111-1111-111111111111.json"
    )
    assert (tmp_path / "raw/api/grants_gov/2026-10-07/search-page-0001.json").exists()
    replayed = list(replay_grants_gov(archive))
    assert sorted(o.content_hash() for o in replayed) == sorted(
        o.content_hash() for o in live
    )


@respx.mock
def test_sam_bulk_archives_csv_and_replays(tmp_path: Path):
    respx.get(SAM_BULK_URL).mock(
        return_value=httpx.Response(
            200, content=Path("tests/fixtures/sam_gov/bulk_sample.csv").read_bytes()
        )
    )
    store = LocalBlobStore(tmp_path / "blobs")
    archive = RawArchive(store, "sam_gov", DAY)
    with build_client() as c:
        live = list(
            SamBulkAdapter(
                c, cache_path=tmp_path / "sam.csv", archive=archive
            ).iter_opportunities()
        )
    assert (
        live[0].raw_uri
        == "raw/api/sam_gov/2026-10-07/ContractOpportunitiesFullCSV.csv#n-101"
    )
    assert [o.source_id for o in replay_sam_bulk(archive)] == [
        o.source_id for o in live
    ]
