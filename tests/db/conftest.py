import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from db.session import make_session_factory

TEST_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+psycopg://grant:grant@localhost:5433/grant_capture_test",
)


def _alembic_config() -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", TEST_URL)
    return cfg


@pytest.fixture(scope="session")
def migrated_engine():
    engine = create_engine(TEST_URL, pool_pre_ping=True)
    try:
        with engine.connect() as conn:
            conn.execute(text("select 1"))
    except OperationalError as exc:
        if os.environ.get("REQUIRE_DB") == "1":
            raise
        pytest.skip(
            f"test database unavailable ({exc.__class__.__name__}); run docker compose up -d db"
        )
    cfg = _alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(migrated_engine):
    with migrated_engine.begin() as conn:
        conn.execute(
            text(
                "TRUNCATE ingest_runs, runs, drafts, saved_opportunities, eligibility_verdicts, "
                "solicitation_briefs, chunks, documents, companies, opportunities CASCADE"
            )
        )
    session = make_session_factory(migrated_engine)()
    yield session
    session.close()
