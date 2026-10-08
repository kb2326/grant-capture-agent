import httpx
import pytest
import respx
from tenacity import wait_none

from ingest.http import build_client, download, request_json


@respx.mock
def test_retries_on_503_then_succeeds():
    route = respx.get("https://api.test/x").mock(
        side_effect=[httpx.Response(503), httpx.Response(200, json={"ok": True})]
    )
    with build_client() as c:
        assert request_json(c, "GET", "https://api.test/x", wait=wait_none()) == {
            "ok": True
        }
    assert route.call_count == 2


@respx.mock
def test_client_error_is_not_retried():
    route = respx.get("https://api.test/bad").mock(return_value=httpx.Response(400))
    with build_client() as c, pytest.raises(httpx.HTTPStatusError):
        request_json(c, "GET", "https://api.test/bad", wait=wait_none())
    assert route.call_count == 1


@respx.mock
def test_download_respects_cap_by_header_and_by_stream():
    respx.get("https://f.test/big").mock(
        return_value=httpx.Response(
            200, headers={"content-length": "999999999"}, content=b"x"
        )
    )
    respx.get("https://f.test/sneaky").mock(
        return_value=httpx.Response(200, content=b"x" * 2048)
    )
    respx.get("https://f.test/ok").mock(
        return_value=httpx.Response(200, content=b"%PDF-1.7")
    )
    with build_client() as c:
        assert download(c, "https://f.test/big", max_bytes=1024) is None
        assert download(c, "https://f.test/sneaky", max_bytes=1024) is None
        assert download(c, "https://f.test/ok", max_bytes=1024) == b"%PDF-1.7"
