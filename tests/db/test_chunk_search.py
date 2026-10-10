import pytest

from db.models import ChunkRow, DocumentRow
from rag.chunks import search_chunks

pytestmark = pytest.mark.db


def _vec(i):
    v = [0.0] * 768
    v[i] = 1.0
    return v


def test_search_chunks_is_hybrid_and_filters_by_corpus(db_session, make_opp):
    comp = DocumentRow(corpus="company", gcs_uri="u", title="a.md", sha256="1")
    sol = DocumentRow(
        corpus="solicitation",
        opportunity_id=make_opp().id,
        gcs_uri="u",
        title="s.pdf",
        sha256="2",
    )
    db_session.add_all([comp, sol])
    db_session.flush()
    db_session.add_all(
        [
            ChunkRow(
                document_id=comp.id,
                ord=0,
                section_path="a.md > Lab",
                text="OPAL-RT rig in the lab",
                n_tokens=5,
                embedding=_vec(0),
            ),
            ChunkRow(
                document_id=comp.id,
                ord=1,
                section_path="a.md > Team",
                text="Maya Okafor leads",
                n_tokens=3,
                embedding=_vec(1),
            ),
            ChunkRow(
                document_id=comp.id,
                ord=2,
                section_path="a.md > New",
                text="unembedded fault scenarios",
                n_tokens=3,
            ),
            ChunkRow(
                document_id=sol.id,
                ord=0,
                section_path="s.pdf",
                text="OPAL-RT required",
                n_tokens=3,
                embedding=_vec(0),
            ),
        ]
    )
    db_session.commit()
    hits = search_chunks(db_session, query_text="OPAL-RT", query_vec=_vec(0))
    assert hits[0].text == "OPAL-RT rig in the lab" and all(
        h.document_title == "a.md" for h in hits
    )
    assert any(
        h.text.startswith("unembedded")
        for h in search_chunks(
            db_session, query_text="fault scenarios", query_vec=_vec(5)
        )
    )
