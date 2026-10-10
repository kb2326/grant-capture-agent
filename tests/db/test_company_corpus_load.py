import pytest
from sqlalchemy import func, select

from db.models import ChunkRow, DocumentRow
from ingest.company_corpus import BANNER, load_company_docs
from ingest.storage import LocalBlobStore

pytestmark = pytest.mark.db


def test_load_is_idempotent_and_marks_company_corpus(db_session, tmp_path):
    docs = tmp_path / "docs"
    docs.mkdir()
    (docs / "a.md").write_text(
        f"{BANNER}\n# A\n## One\n" + "Text one. " * 50, encoding="utf-8"
    )
    (docs / "b.md").write_text(
        f"{BANNER}\n# B\n## Two\n" + "Text two. " * 50, encoding="utf-8"
    )
    plan = {
        "originals": ["a.md"],
        "new": [{"file": "b.md", "kind": "outdated", "phrases": []}],
    }
    store = LocalBlobStore(tmp_path / "blobs")
    first = load_company_docs(db_session, store, docs, plan)
    assert first["stored"] == 2 and first["chunks"] >= 2
    assert load_company_docs(db_session, store, docs, plan)["unchanged"] == 2
    rows = db_session.scalars(
        select(DocumentRow).where(DocumentRow.corpus == "company")
    ).all()
    assert {r.title for r in rows} == {"a.md", "b.md"} and all(
        r.opportunity_id is None for r in rows
    )
    assert (
        db_session.scalar(select(func.count()).select_from(ChunkRow)) == first["chunks"]
    )
