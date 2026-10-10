"""Company chunks labeled [C1..Cn] for drafting prompts; labels map back to chunk ids."""

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import ChunkRow, DocumentRow


@dataclass(frozen=True)
class LabeledChunk:
    label: str
    chunk_id: uuid.UUID
    document_title: str
    section_path: str
    text: str


def label_chunks(rows: list[tuple[uuid.UUID, str, str, str]]) -> list[LabeledChunk]:
    return [
        LabeledChunk(f"C{i}", cid, title, path, txt)
        for i, (cid, title, path, txt) in enumerate(rows, 1)
    ]


def load_company_chunks(session: Session) -> list[LabeledChunk]:
    rows = session.execute(
        select(ChunkRow.id, DocumentRow.title, ChunkRow.section_path, ChunkRow.text)
        .join(DocumentRow, DocumentRow.id == ChunkRow.document_id)
        .where(DocumentRow.corpus == "company")
        .order_by(DocumentRow.title, ChunkRow.ord)
    )
    return label_chunks([tuple(r) for r in rows])


def render_chunks(chunks: list[LabeledChunk]) -> str:
    return "\n\n".join(
        f"[{c.label}] {c.document_title} > {c.section_path.split(' > ')[-1]}\n{c.text}"
        for c in chunks
    )
