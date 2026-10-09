from collections.abc import Iterator
from typing import Protocol

from ingest.models import Opportunity


class SourceAdapter(Protocol):
    name: str

    def iter_opportunities(self, limit: int | None = None) -> Iterator[Opportunity]: ...
