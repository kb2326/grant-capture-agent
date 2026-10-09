"""HTTP helpers: retrying JSON requests and size-capped downloads."""

from typing import Any

import httpx
from tenacity import (
    Retrying,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)
from tenacity.wait import wait_base

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
DEFAULT_WAIT = wait_exponential(multiplier=0.5, max=20)
USER_AGENT = "grant-capture-agent/0.1 (+https://github.com/kb2326/grant-capture-agent)"


class RetryableHTTPError(Exception):
    pass


def build_client(timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(
        timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True
    )


def request_json(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    max_attempts: int = 5,
    wait: wait_base = DEFAULT_WAIT,
    **kwargs: Any,
) -> Any:
    for attempt in Retrying(
        stop=stop_after_attempt(max_attempts),
        wait=wait,
        retry=retry_if_exception_type((RetryableHTTPError, httpx.TransportError)),
        reraise=True,
    ):
        with attempt:
            response = client.request(method, url, **kwargs)
            if response.status_code in RETRYABLE_STATUS:
                raise RetryableHTTPError(f"{response.status_code} from {url}")
            response.raise_for_status()
            return response.json()
    raise AssertionError("unreachable")


def download(client: httpx.Client, url: str, *, max_bytes: int) -> bytes | None:
    with client.stream("GET", url) as response:
        response.raise_for_status()
        declared = response.headers.get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > max_bytes:
            return None
        chunks: list[bytes] = []
        total = 0
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > max_bytes:
                return None
            chunks.append(chunk)
        return b"".join(chunks)


def filename_from_disposition(header: str | None) -> str | None:
    import re
    from urllib.parse import unquote

    if not header:
        return None
    star = re.search(r"filename\*\s*=\s*[^']*''([^;]+)", header)
    if star:
        return unquote(star.group(1).strip().strip('"'))
    plain = re.search(r'filename\s*=\s*"?([^";]+)"?', header)
    return plain.group(1).strip() if plain else None


def download_named(
    client: httpx.Client, url: str, *, max_bytes: int
) -> tuple[bytes | None, str | None, str | None]:
    with client.stream("GET", url) as response:
        response.raise_for_status()
        name = filename_from_disposition(response.headers.get("content-disposition"))
        ctype = response.headers.get("content-type")
        declared = response.headers.get("content-length")
        if declared is not None and declared.isdigit() and int(declared) > max_bytes:
            return None, name, ctype
        chunks, total = [], 0
        for chunk in response.iter_bytes():
            total += len(chunk)
            if total > max_bytes:
                return None, name, ctype
            chunks.append(chunk)
        return b"".join(chunks), name, ctype
