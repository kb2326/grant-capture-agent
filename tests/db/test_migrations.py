import pytest
from sqlalchemy import inspect, text

pytestmark = pytest.mark.db

EXPECTED_TABLES = {
    "opportunities",
    "documents",
    "chunks",
    "companies",
    "solicitation_briefs",
    "eligibility_verdicts",
    "saved_opportunities",
    "drafts",
    "runs",
    "ingest_runs",
}


def test_all_tables_exist(migrated_engine):
    assert EXPECTED_TABLES <= set(inspect(migrated_engine).get_table_names())


def test_vector_extension_and_indexes(migrated_engine):
    with migrated_engine.connect() as conn:
        assert (
            conn.execute(
                text("select 1 from pg_extension where extname='vector'")
            ).scalar()
            == 1
        )
        idx = dict(
            conn.execute(
                text(
                    "select indexname, indexdef from pg_indexes where tablename='chunks'"
                )
            ).all()
        )
    assert "hnsw" in idx["ix_chunks_embedding_hnsw"]
    assert "vector_cosine_ops" in idx["ix_chunks_embedding_hnsw"]
    assert "gin" in idx["ix_chunks_tsv"]


def test_tsv_is_generated(migrated_engine):
    with migrated_engine.begin() as conn:
        opp = conn.execute(
            text(
                "insert into opportunities (id, source, source_id, kind, title, agency, summary, url, status, "
                "naics, assistance_listings, eligibility_codes, raw, content_hash) values "
                "(gen_random_uuid(), 't', '1', 'grant', 't', 'a', '', 'u', 'open', '{}', '{}', '{}', '{}', 'h') "
                "returning id"
            )
        ).scalar()
        doc = conn.execute(
            text(
                "insert into documents (id, opportunity_id, corpus, gcs_uri, title, parse_status, sha256) values "
                "(gen_random_uuid(), :o, 'solicitation', 'file:///x', 'x', 'pending', 's') returning id"
            ),
            {"o": opp},
        ).scalar()
        tsv = conn.execute(
            text(
                "insert into chunks (id, document_id, ord, section_path, text, n_tokens) values "
                "(gen_random_uuid(), :d, 0, 'Eligibility', 'small business concerns', 3) returning tsv::text"
            ),
            {"d": doc},
        ).scalar()
        conn.execute(text("delete from opportunities"))
    assert "small" in tsv and "elig" in tsv
