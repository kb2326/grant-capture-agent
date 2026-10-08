---
name: ingest-status
description: Report the state of grant-capture-agent ingestion - row counts by source and status, documents stored, the last runs and their data-quality issues. Use when asked "how is the data", "did ingestion work", or before starting work that depends on fresh data.
---

1. Make sure the local DB is up: `docker compose ps db` (start with `docker compose up -d db` if needed).
2. Run `uv run python -m ingest stats`.
3. Show the last 5 runs with their quality issues:
   `uv run python -c "from sqlalchemy import select; from app.config import get_settings; from db.models import IngestRunRow; from db.session import make_engine, make_session_factory; s=make_session_factory(make_engine(get_settings().database_url))(); [print(r.started_at, r.stats.get('source'), r.stats.get('seen'), r.stats.get('quality_issues')) for r in s.scalars(select(IngestRunRow).order_by(IngestRunRow.started_at.desc()).limit(5))]"`
4. Summarize in plain English: totals per source, anything that failed, any quality error or warning, and whether a re-run or replay is needed.
