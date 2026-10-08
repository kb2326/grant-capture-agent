"""Raw zone (bronze): source responses archived unchanged, partitioned by source and date."""

import csv
import io
import json
import re
from collections.abc import Callable, Iterator
from datetime import date
from typing import Any

from ingest.models import Opportunity
from ingest.storage import BlobStore

_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")
SAM_CSV_NAME = "ContractOpportunitiesFullCSV.csv"


class RawArchive:
    def __init__(self, store: BlobStore, source: str, run_date: date) -> None:
        self.store = store
        self.prefix = f"raw/api/{source}/{run_date:%Y-%m-%d}/"

    def key(self, name: str) -> str:
        parts = (part.replace("..", "") for part in name.replace("\\", "/").split("/"))
        segments = [part for part in parts if part not in ("", ".")]
        cleaned = _UNSAFE.sub("_", "_".join(segments)).strip("._")
        return self.prefix + (cleaned or "unnamed")

    def put_json(self, name: str, payload: Any) -> str:
        key = self.key(name if name.endswith(".json") else f"{name}.json")
        self.store.put(key, json.dumps(payload, sort_keys=True).encode("utf-8"))
        return key

    def put_bytes(self, name: str, data: bytes) -> str:
        key = self.key(name)
        self.store.put(key, data)
        return key

    def iter_json(self, name_prefix: str = "") -> Iterator[tuple[str, Any]]:
        for key in self.store.list(self.prefix + name_prefix):
            if key.endswith(".json"):
                yield key, json.loads(self.store.get(key))


def replay_grants_gov(archive: RawArchive) -> Iterator[Opportunity]:
    from ingest.sources.grants_gov import map_grants_gov

    for key, payload in archive.iter_json("detail-"):
        yield map_grants_gov(payload["data"]).model_copy(update={"raw_uri": key})


def replay_sam_bulk(
    archive: RawArchive, naics: frozenset[str] | None = None
) -> Iterator[Opportunity]:
    from ingest.sources.sam_gov import R_AND_D_NAICS
    from ingest.sources.sam_gov_bulk import BASE_TYPES, map_sam_csv_row

    allowed = naics or frozenset(R_AND_D_NAICS)
    key = archive.key(SAM_CSV_NAME)
    text = archive.store.get(key).decode("utf-8", errors="replace")
    for row in csv.DictReader(io.StringIO(text, newline="")):
        if (row.get("NaicsCode") or "").strip() in allowed and (
            row.get("BaseType") or ""
        ).strip() in BASE_TYPES:
            o = map_sam_csv_row(row)
            yield o.model_copy(update={"raw_uri": f"{key}#{o.source_id}"})


class ReplayAdapter:
    def __init__(
        self, name: str, version: str, factory: Callable[[], Iterator[Opportunity]]
    ) -> None:
        self.name, self.version, self._factory = name, f"{version}+replay", factory

    def iter_opportunities(self, limit: int | None = None) -> Iterator[Opportunity]:
        for i, o in enumerate(self._factory()):
            if limit is not None and i >= limit:
                return
            yield o
