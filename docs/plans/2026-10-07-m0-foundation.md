# M0 Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A scaffolded, tested and CI-checked repository that ingests real Grants.gov and SAM.gov opportunities (with attachments) into Postgres + pgvector locally and on Cloud SQL, with the eval harness, synthetic company data, ADRs and Terraform-managed Google Cloud foundation in place.

**Architecture:** Part A builds everything locally. The agents-cli `adk` scaffold provides the agent app, deployment templates and the eval layout. A small `ingest/` package fetches from the source APIs, archives every raw response unchanged in a raw zone, normalizes each record to a CommonGrants-compatible `Opportunity` with provenance, stores attachments in a blob store, runs data-quality checks after each run, and upserts rows through SQLAlchemy into a schema managed by Alembic. Part B provisions the cloud foundation with Terraform (GCS, Secret Manager, Artifact Registry, Cloud SQL with pgvector, service accounts, Workload Identity Federation), then runs the same ingestion as a Cloud Run Job against Cloud SQL and GCS.

**Tech Stack:** Python 3.12 · uv · agents-cli 1.9 / google-adk 2.x · pydantic 2 + pydantic-settings · httpx + tenacity · SQLAlchemy 2 + psycopg 3 + Alembic + pgvector · typer · pytest + respx · Docker (pgvector/pgvector:pg16) · Terraform ≥ 1.9 (google provider 6.x) · GitHub Actions

**Spec:** [`docs/design/system-design.md`](../design/system-design.md) (§3 layout, §4 ingestion, §5 data model, §11 evaluation, §14 environments, §16 platform capabilities, §17 M0 criteria, §18 ADRs) and [`docs/product/PRD.md`](../product/PRD.md) §7 data sources.

## Global Constraints

- GCP project `grant-capture-agent` (number 313052279552), region `us-central1`, owner account `karthickbalaje01@gmail.com`. Never use the `karthick@tennisbrat.com` account.
- Monthly budget $10 USD (alerts only). Cloud SQL exists only while it's in use: `scripts/cloudsql.sh down` between short breaks, `terraform apply -var enable_cloudsql=false` at the end of a milestone (a stopped instance still pays about $7/month for its IPv4 address).
- Models (pinned, verified 2026-10-07): `gemini-3.8-flash`, `gemini-3.5-flash-lite`, `gemini-3.1-pro-preview` at location `global`; embeddings `gemini-embedding-001`, 768 dimensions, at `us-central1`.
- Python `>=3.11,<3.14` (scaffold constraint); CI uses 3.12.
- Indexed sources: Grants.gov (Simpler Grants API, header `X-API-Key`) and SAM.gov Opportunities API v2 (`api_key` query parameter). Never call the SBIR.gov API or the DoD DSIP portal.
- Simpler Grants keys allow 60 requests/minute and 10,000/day, and are disabled after 30 days unused. The adapter waits at least `GRANTS_MIN_INTERVAL_S` (default 1.1 s) between requests.
- SAM.gov notices come from the **public daily bulk extract** (`ContractOpportunitiesFullCSV.csv`, about 210 MB, refreshed daily, no key, includes full descriptions). The SAM.gov API is used only for on-demand attachment lookups, because public keys allow about 10 requests per day. The adapter must never exceed `SAM_DAILY_REQUEST_BUDGET` (default 8).
- SAM.gov R&D NAICS codes: `541713`, `541714`, `541715`. Notice types: `o`, `p`, `k`.
- Normalized records export to the official CommonGrants `OpportunityBase` model (`common-grants-sdk`), validated, and stored in `opportunities.raw`.
- Opportunity statuses stored: `forecasted`, `open`, `closed`, `custom`. Kinds: `grant`, `sbir`, `sttr`, `contract`.
- Attachments: only `application/pdf`, `application/vnd.openxmlformats-officedocument.wordprocessingml.document`, `application/msword`, `text/html`, `text/plain`, each ≤ 25 MB.
- Secrets are never committed. `.env` is git-ignored; cloud secrets live in Secret Manager.
- Never assert on LLM output text in pytest. Agent behaviour belongs in `agents-cli eval`.
- Repo text never mentions any commercial product used as inspiration.
- Every commit message ends with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

1. **SAM.gov's tiny daily quota.** A long run, a retry storm or a re-run on the same day must not burn the key's ~10 requests. Expected: the adapter counts requests and stops cleanly at the budget, without raising, and logs that it stopped. *(Test added in Task 7.)*
2. **Hostile or odd attachment file names** (`../../etc/passwd`, `Résumé (final).PDF`, empty name). Expected: the stored key stays under `raw/<source>/<source_id>/` and is filesystem-safe. *(Test added in Task 5.)*
3. **Re-running or replaying ingestion.** Expected: unchanged opportunities aren't updated and their attachments aren't re-downloaded; a changed opportunity is updated in place, not duplicated; replaying the raw zone reproduces identical records. *(Tests added in Tasks 8 and 8b.)*
4. **Oversized or non-document attachments** (a 200 MB zip, an `.xlsx`). Expected: they're skipped and counted in the stats, never downloaded in full. *(Test added in Task 5.)*
5. **Missing or odd API fields** (`summary: null`, `close_date: null`, `award_ceiling: null`, SAM `responseDeadLine` with a timezone offset, `resourceLinks: null`). Expected: mapping still produces a valid `Opportunity`; nothing crashes the run. *(Tests added in Tasks 6 and 7.)*

---

## File Structure

```
.github/workflows/ci.yml                 NEW  lint, types, unit + db tests, eval smoke
.github/workflows/{pr_checks,staging,deploy-to-prod}.yaml   SCAFFOLD, set to manual-only until M4
.pre-commit-config.yaml                  NEW  ruff, ruff-format, codespell, unit tests on pre-push
CLAUDE.md / AGENTS.md                    SCAFFOLD + NEW  conventions for coding agents
docker-compose.yml                       NEW  local Postgres 16 + pgvector on port 5433
db/init/01-test-db.sql                   NEW  creates grant_capture_test
alembic.ini, db/migrations/              NEW  Alembic environment + initial revision
db/models.py                             NEW  SQLAlchemy models for every §5 table
db/session.py                            NEW  engine/session factory
app/agent.py                             SCAFFOLD, modified  root agent placeholder (no weather tools)
app/config.py                            NEW  Settings (models, DB, keys, budgets)
ingest/__init__.py, ingest/__main__.py   NEW  typer CLI: run, seed-company, stats
ingest/models.py                         NEW  CommonGrants-compatible Opportunity + helpers
ingest/http.py                           NEW  retrying JSON client + capped downloader
ingest/storage.py                        NEW  BlobStore protocol, LocalBlobStore, GCSBlobStore, safe_key
ingest/sources/base.py                   NEW  SourceAdapter protocol
ingest/sources/grants_gov.py             NEW  Simpler Grants adapter + mapper
ingest/sources/sam_gov.py                NEW  SAM.gov API adapter + request budget (on-demand)
ingest/sources/sam_gov_bulk.py           NEW  SAM.gov daily bulk CSV adapter (primary)
ingest/pipeline.py                       NEW  upsert + attachment handling + run stats + provenance
ingest/raw.py                            NEW  raw zone (bronze) archive + replay
ingest/quality.py                        NEW  post-run data-quality checks
ingest/company.py                        NEW  seed the companies table from profile.json
data/company/profile.json, data/company/docs/*.md   NEW  synthetic Lumen Grid Labs
evals/metrics.py, evals/report.py, evals/run.py, evals/LABELING.md, evals/data/{golden,dev}/README.md   NEW
docs/adr/0000-template.md, 0001…0009, 0012…0015    NEW
deployment/terraform/foundation/*.tf     NEW  cloud foundation (Part B)
Dockerfile.ingest                        NEW  ingestion image
scripts/bootstrap_tf_state.sh, scripts/cloudsql.sh, scripts/secrets_put.sh   NEW
tests/unit/…, tests/db/…, tests/fixtures/…   NEW
```

`tests/integration/` and `tests/eval/` are the scaffold's agent tests (they call Gemini). They stay as they are, run manually in M0, and join CI in M4.

---

# Part A: Local foundation

### Task 1: Scaffold the agents-cli project into the repo

**Files:**
- Create (from scaffold): `app/`, `deployment/`, `tests/`, `Dockerfile`, `pyproject.toml`, `uv.lock`, `agents-cli-manifest.yaml`, `.env.example`, `CLAUDE.md`, `.github/workflows/*.yaml`, `.gcloudignore`
- Modify: `.gitignore` (merge), `app/agent.py`, `.github/workflows/{pr_checks,staging,deploy-to-prod}.yaml`
- Test: `tests/unit/test_agent_wiring.py`

**Interfaces:**
- Produces: package `app` with `app.agent.root_agent` (an ADK `Agent` named `grant_capture_agent`) and `app.agent.app` (ADK `App`).

- [ ] **Step 1: Generate the scaffold in a temporary directory**

```bash
TMP=$(mktemp -d)
agents-cli scaffold create grant-capture-agent -a adk -dir app -d agent_runtime \
  --cicd-runner github_actions --agent-guidance-filename CLAUDE.md --bq-analytics \
  --region us-central1 -y -s -o "$TMP"
ls "$TMP/grant-capture-agent"
```
Expected: the listing shows `app/ deployment/ tests/ Dockerfile pyproject.toml uv.lock agents-cli-manifest.yaml CLAUDE.md README.md .github/`.

- [ ] **Step 2: Copy into the repo without overwriting our README or docs**

```bash
SRC="$TMP/grant-capture-agent"
cp -r "$SRC/app" "$SRC/deployment" "$SRC/tests" "$SRC/.github" .
cp "$SRC/Dockerfile" "$SRC/pyproject.toml" "$SRC/uv.lock" "$SRC/agents-cli-manifest.yaml" \
   "$SRC/.env.example" "$SRC/CLAUDE.md" "$SRC/.gcloudignore" "$SRC/deployment_metadata.json" .
cat "$SRC/.gitignore" >> .gitignore
printf '\n# grant-capture-agent\n.env\ndata/blobs/\nreports/\n.terraform/\n*.tfstate*\n' >> .gitignore
```
Do **not** copy the scaffold's `README.md` or `.env` (the scaffold `.env` holds placeholder values; ours is created in Task 2).

- [ ] **Step 3: Make the scaffold's deploy workflows manual-only until M4**

In each of `.github/workflows/pr_checks.yaml`, `staging.yaml` and `deploy-to-prod.yaml`, replace the whole `on:` block with:

```yaml
on:
  workflow_dispatch: {}  # enabled in M4 once Workload Identity Federation secrets exist
```

- [ ] **Step 4: Write the failing wiring test**

```python
# tests/unit/test_agent_wiring.py
from app.agent import app, root_agent


def test_root_agent_identity():
    assert root_agent.name == "grant_capture_agent"
    assert app.root_agent is root_agent


def test_root_agent_has_no_demo_tools():
    tool_names = {getattr(t, "__name__", str(t)) for t in root_agent.tools}
    assert "get_weather" not in tool_names
    assert "get_current_time" not in tool_names
```

- [ ] **Step 5: Run it to see it fail**

Run: `uv sync && uv run pytest tests/unit/test_agent_wiring.py -v`
Expected: `test_root_agent_has_no_demo_tools` FAILS (the scaffold ships the weather demo tools).

- [ ] **Step 6: Replace the demo agent body**

In `app/agent.py`, delete `get_weather` and `get_current_time` and their imports (`datetime`, `ZoneInfo`), and change the `root_agent` definition to:

```python
root_agent = Agent(
    # Keep in sync with agents-cli-manifest.yaml (root_agent_name).
    name="grant_capture_agent",
    model=Gemini(
        model=MODEL,
        retry_options=types.HttpRetryOptions(attempts=3),
    ),
    instruction=(
        "You are the grant-capture assistant for a small R&D company. "
        "The Discover, Analyze and Draft workflows are not connected yet. "
        "If asked to find, analyze or draft, say which milestone adds that capability "
        "(Analyze: M1, Discover: M2, Draft: M3) and do not invent results."
    ),
    tools=[],
)
```
Leave `MODEL = "gemini-3.8-flash"` and the BigQuery Agent Analytics block unchanged (Principle 1: preserve scaffold config).

- [ ] **Step 7: Run unit tests and a smoke run**

Run: `uv run pytest tests/unit -v`
Expected: all PASS (including the scaffold's `test_dummy.py`).

Run: `agents-cli run "What can you do today?"`
Expected: a short answer naming M1/M2/M3; no tool calls. This costs well under $0.01.

- [ ] **Step 8: Commit**

```bash
git add app deployment tests .github Dockerfile pyproject.toml uv.lock agents-cli-manifest.yaml \
  .env.example CLAUDE.md .gcloudignore deployment_metadata.json .gitignore
git commit -m "feat(m0): scaffold ADK project with agents-cli (adk, agent_runtime, github_actions)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Settings, dependencies and coding-agent conventions

**Files:**
- Create: `app/config.py`, `.pre-commit-config.yaml`, `AGENTS.md`
- Modify: `pyproject.toml`, `.env.example`, `CLAUDE.md`
- Test: `tests/unit/test_config.py`

**Interfaces:**
- Produces: `app.config.Settings` (fields below) and `app.config.get_settings() -> Settings` (cached).

- [ ] **Step 1: Add dependencies and tool config**

```bash
uv add "pydantic-settings>=2.6" "httpx>=0.28" "tenacity>=9.0" "sqlalchemy>=2.0.36" \
  "psycopg[binary]>=3.2" "alembic>=1.14" "pgvector>=0.3.6" "typer>=0.15" \
  "google-cloud-storage>=2.19" "google-cloud-secret-manager>=2.22" \
  "common-grants-sdk>=0.8.1"
uv add --dev "respx>=0.22" "pre-commit>=4.0"
```
In `pyproject.toml`, change `[tool.hatch.build.targets.wheel] packages = ["app","frontend"]` to `packages = ["app", "ingest", "db", "evals"]` and `known-first-party = ["app", "frontend"]` to `known-first-party = ["app", "ingest", "db", "evals"]`. Add:

```toml
[tool.pytest.ini_options]
pythonpath = "."
asyncio_default_fixture_loop_scope = "session"
markers = ["db: needs a Postgres database (TEST_DATABASE_URL)"]
```
(replacing the existing `[tool.pytest.ini_options]` block).

- [ ] **Step 2: Write the failing test**

```python
# tests/unit/test_config.py
from app.config import Settings


def test_defaults_match_pinned_models(monkeypatch):
    for var in ("MODEL_AGENT", "MODEL_GRADER", "MODEL_DRAFTER", "MODEL_EMBEDDING"):
        monkeypatch.delenv(var, raising=False)
    s = Settings(_env_file=None)
    assert s.google_cloud_project == "grant-capture-agent"
    assert s.model_agent == "gemini-3.8-flash"
    assert s.model_grader == "gemini-3.5-flash-lite"
    assert s.model_drafter == "gemini-3.1-pro-preview"
    assert s.model_embedding == "gemini-embedding-001"
    assert s.embedding_dim == 768
    assert s.embedding_location == "us-central1"
    assert s.sam_daily_request_budget == 8


def test_env_overrides_and_secret_masking(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:p@h:1/d")
    monkeypatch.setenv("SAM_API_KEY", "abc123")
    s = Settings(_env_file=None)
    assert s.database_url == "postgresql+psycopg://u:p@h:1/d"
    assert s.sam_api_key is not None
    assert s.sam_api_key.get_secret_value() == "abc123"
    assert "abc123" not in repr(s)
```

- [ ] **Step 3: Run it to see it fail**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.config'`.

- [ ] **Step 4: Implement `app/config.py`**

```python
"""Runtime settings, loaded from the environment and an optional .env file."""

from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    google_cloud_project: str = "grant-capture-agent"
    google_cloud_location: str = "global"
    embedding_location: str = "us-central1"

    model_agent: str = "gemini-3.8-flash"
    model_grader: str = "gemini-3.5-flash-lite"
    model_drafter: str = "gemini-3.1-pro-preview"
    model_embedding: str = "gemini-embedding-001"
    embedding_dim: int = 768

    database_url: str = "postgresql+psycopg://grant:grant@localhost:5433/grant_capture"
    blob_root: str = "data/blobs"  # local path, or gs://bucket for GCS

    simpler_grants_api_key: SecretStr | None = None
    sam_api_key: SecretStr | None = None
    sam_daily_request_budget: int = 8

    max_attachment_bytes: int = 25 * 1024 * 1024


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: PASS.

- [ ] **Step 6: Update `.env.example`, create local `.env`**

Append to `.env.example`:

```bash
# Data
DATABASE_URL=postgresql+psycopg://grant:grant@localhost:5433/grant_capture
BLOB_ROOT=data/blobs
# Source API keys (free): simpler.grants.gov developer page; sam.gov Account Details
SIMPLER_GRANTS_API_KEY=
SAM_API_KEY=
SAM_DAILY_REQUEST_BUDGET=8
```
Then `cp .env.example .env` and set `GOOGLE_CLOUD_PROJECT=grant-capture-agent`, `GOOGLE_CLOUD_LOCATION=global`. `.env` is git-ignored (Task 1).

- [ ] **Step 7: Pre-commit hooks**

```yaml
# .pre-commit-config.yaml
repos:
  - repo: https://github.com/astral-sh/ruff-pre-commit
    rev: v0.8.6
    hooks:
      - id: ruff
        args: [--fix]
      - id: ruff-format
  - repo: https://github.com/codespell-project/codespell
    rev: v2.3.0
    hooks:
      - id: codespell
        args: [--skip, "uv.lock,*.json,legacy/*"]
  - repo: local
    hooks:
      - id: unit-tests
        name: unit tests
        entry: uv run pytest tests/unit -q
        language: system
        pass_filenames: false
        stages: [pre-push]
```
Run: `uv run pre-commit install --hook-type pre-commit --hook-type pre-push && uv run pre-commit run --all-files`
Expected: passes (ruff may auto-fix formatting on the first run; re-run until clean).

- [ ] **Step 8: Coding-agent conventions**

Append to the scaffold-generated `CLAUDE.md`:

```markdown
## Project conventions (grant-capture-agent)

- Read `docs/design/system-design.md` before changing behaviour; plans live in `docs/plans/`.
- Packages: `app/` (ADK agents), `ingest/` (data sources + pipeline), `rag/` (retrieval library, M1+), `db/` (models + migrations), `evals/` (metric harness).
- Tests: `tests/unit` (no network, no DB), `tests/db` (needs `docker compose up -d db`), `tests/integration` + `tests/eval` (call Gemini; run manually).
- Never assert on LLM output text in pytest; use `agents-cli eval run`.
- Eligibility and verification decisions are plain Python in `app/rules/`, never model judgements.
- Models and thresholds come from `app/config.py`; don't hard-code model IDs elsewhere.
- GCP: project `grant-capture-agent`, personal account only. Stop Cloud SQL after use: `scripts/cloudsql.sh down`.
- Commits: conventional prefix (`feat`, `fix`, `docs`, `test`, `chore`, `infra`) and the Co-Authored-By trailer.
```

Create `AGENTS.md`:

```markdown
# AGENTS.md

Coding-agent guidance for this repository lives in [CLAUDE.md](CLAUDE.md), the single source of truth for conventions, commands and architecture pointers.
```

- [ ] **Step 9: Commit**

```bash
git add pyproject.toml uv.lock app/config.py tests/unit/test_config.py .env.example \
  .pre-commit-config.yaml CLAUDE.md AGENTS.md
git commit -m "feat(m0): settings, dependencies, pre-commit and coding-agent conventions

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Postgres + pgvector schema with Alembic

**Files:**
- Create: `docker-compose.yml`, `db/init/01-test-db.sql`, `db/__init__.py`, `db/models.py`, `db/session.py`, `alembic.ini`, `db/migrations/env.py`, `db/migrations/script.py.mako`, `db/migrations/versions/0001_initial_schema.py` (generated, then edited)
- Test: `tests/db/conftest.py`, `tests/db/test_migrations.py`

**Interfaces:**
- Consumes: `app.config.get_settings().database_url`.
- Produces: `db.models.Base` and row classes `OpportunityRow`, `DocumentRow`, `ChunkRow`, `CompanyRow`, `SolicitationBriefRow`, `EligibilityVerdictRow`, `SavedOpportunityRow`, `DraftRow`, `RunRow`, `IngestRunRow`; `db.models.EMBEDDING_DIM = 768`; `db.session.make_engine(url: str) -> Engine`; `db.session.make_session_factory(engine: Engine) -> sessionmaker[Session]`; pytest fixture `db_session` (in `tests/db/conftest.py`) yielding a `Session` on a freshly migrated test database.

- [ ] **Step 1: Local database**

```yaml
# docker-compose.yml
services:
  db:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: grant
      POSTGRES_PASSWORD: grant
      POSTGRES_DB: grant_capture
    ports: ["5433:5432"]
    volumes:
      - pgdata:/var/lib/postgresql/data
      - ./db/init:/docker-entrypoint-initdb.d:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U grant"]
      interval: 5s
      retries: 10
volumes:
  pgdata: {}
```

```sql
-- db/init/01-test-db.sql
CREATE DATABASE grant_capture_test;
```
Run: `docker compose up -d db && docker compose ps`
Expected: `db` is `healthy`.

- [ ] **Step 2: Write the models**

```python
# db/models.py
"""SQLAlchemy models for the system-design §5 schema."""

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    Computed,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

EMBEDDING_DIM = 768


class Base(DeclarativeBase):
    pass


def _uuid_pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now())


class OpportunityRow(Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_opportunities_source"),
        CheckConstraint("kind in ('grant','sbir','sttr','contract')", name="ck_opportunities_kind"),
        CheckConstraint("status in ('forecasted','open','closed','custom')", name="ck_opportunities_status"),
        Index("ix_opportunities_status_close", "status", "close_at"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    source: Mapped[str] = mapped_column(String(32))
    source_id: Mapped[str] = mapped_column(String(128))
    kind: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(Text)
    agency: Mapped[str] = mapped_column(Text)
    summary: Mapped[str] = mapped_column(Text, default="")
    url: Mapped[str] = mapped_column(Text)
    posted_at: Mapped[date | None] = mapped_column(Date)
    close_at: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(16))
    award_floor: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    award_ceiling: Mapped[Decimal | None] = mapped_column(Numeric(16, 2))
    naics: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    assistance_listings: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    eligibility_codes: Mapped[list[str]] = mapped_column(ARRAY(Text), default=list)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB)
    content_hash: Mapped[str] = mapped_column(String(64))
    ingested_at: Mapped[datetime] = _now()
    # provenance: when it was fetched, which raw file it came from, which adapter produced it
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    raw_uri: Mapped[str | None] = mapped_column(Text)
    adapter_version: Mapped[str | None] = mapped_column(String(32))


class DocumentRow(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint("corpus in ('solicitation','company')", name="ck_documents_corpus"),
        UniqueConstraint("opportunity_id", "sha256", name="uq_documents_opportunity_sha"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    opportunity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE")
    )
    corpus: Mapped[str] = mapped_column(String(16))
    gcs_uri: Mapped[str] = mapped_column(Text)
    mime: Mapped[str | None] = mapped_column(String(128))
    title: Mapped[str] = mapped_column(Text)
    page_count: Mapped[int | None] = mapped_column(Integer)
    parse_status: Mapped[str] = mapped_column(String(16), default="pending")
    parse_error: Mapped[str | None] = mapped_column(Text)
    sha256: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = _now()


class ChunkRow(Base):
    __tablename__ = "chunks"
    __table_args__ = (
        Index("ix_chunks_document_ord", "document_id", "ord"),
        Index(
            "ix_chunks_embedding_hnsw",
            "embedding",
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={"embedding": "vector_cosine_ops"},
        ),
        Index("ix_chunks_tsv", "tsv", postgresql_using="gin"),
    )

    id: Mapped[uuid.UUID] = _uuid_pk()
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE")
    )
    ord: Mapped[int] = mapped_column(Integer)
    section_path: Mapped[str] = mapped_column(Text, default="")
    page_start: Mapped[int | None] = mapped_column(Integer)
    page_end: Mapped[int | None] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    n_tokens: Mapped[int] = mapped_column(Integer)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBEDDING_DIM))
    tsv: Mapped[str] = mapped_column(
        TSVECTOR,
        Computed("to_tsvector('english', coalesce(section_path, '') || ' ' || text)", persisted=True),
    )


class CompanyRow(Base):
    __tablename__ = "companies"
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, unique=True)
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB)


class SolicitationBriefRow(Base):
    __tablename__ = "solicitation_briefs"
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True
    )
    brief: Mapped[dict[str, Any]] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = _now()


class EligibilityVerdictRow(Base):
    __tablename__ = "eligibility_verdicts"
    __table_args__ = (
        CheckConstraint("verdict in ('ELIGIBLE','INELIGIBLE','NEEDS_REVIEW')", name="ck_verdicts_verdict"),
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    verdict: Mapped[str] = mapped_column(String(16))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rules_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = _now()


class SavedOpportunityRow(Base):
    __tablename__ = "saved_opportunities"
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE"), primary_key=True
    )
    status: Mapped[str] = mapped_column(String(32), default="pursuing")
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = _now()


class DraftRow(Base):
    __tablename__ = "drafts"
    __table_args__ = (
        CheckConstraint("status in ('pending_review','approved','rejected')", name="ck_drafts_status"),
    )
    id: Mapped[uuid.UUID] = _uuid_pk()
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("opportunities.id", ondelete="CASCADE")
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE")
    )
    section_id: Mapped[str] = mapped_column(String(64))
    draft: Mapped[dict[str, Any]] = mapped_column(JSONB)
    status: Mapped[str] = mapped_column(String(16), default="pending_review")
    created_at: Mapped[datetime] = _now()


class RunRow(Base):
    __tablename__ = "runs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    workflow: Mapped[str] = mapped_column(String(32))
    session_id: Mapped[str | None] = mapped_column(String(128))
    trace_id: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = _now()
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(10, 6), default=0)
    outcome: Mapped[str | None] = mapped_column(String(32))


class IngestRunRow(Base):
    __tablename__ = "ingest_runs"
    id: Mapped[uuid.UUID] = _uuid_pk()
    started_at: Mapped[datetime] = _now()
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stats: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict)
```

```python
# db/session.py
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker


def make_engine(url: str) -> Engine:
    return create_engine(url, pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)
```
Create an empty `db/__init__.py`.

- [ ] **Step 3: Alembic environment**

Run: `uv run alembic init db/migrations` and then move the generated `db/migrations/alembic.ini` if Alembic placed it there, so `alembic.ini` sits at the repo root with `script_location = db/migrations`. Replace `db/migrations/env.py` with:

```python
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

import pgvector.sqlalchemy  # noqa: F401  (registers the vector type for autogenerate)
from app.config import get_settings
from db.models import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)
if not config.get_main_option("sqlalchemy.url"):
    config.set_main_option("sqlalchemy.url", get_settings().database_url)
target_metadata = Base.metadata


def run_migrations_offline() -> None:
    context.configure(url=config.get_main_option("sqlalchemy.url"), target_metadata=target_metadata,
                      literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(config.get_section(config.config_ini_section, {}),
                                     prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
```
In `alembic.ini`, leave `sqlalchemy.url =` empty (env.py fills it from settings).

- [ ] **Step 4: Write the failing migration test**

```python
# tests/db/conftest.py
import os

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

from db.session import make_session_factory

TEST_URL = os.environ.get(
    "TEST_DATABASE_URL", "postgresql+psycopg://grant:grant@localhost:5433/grant_capture_test"
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
        pytest.skip(f"test database unavailable ({exc.__class__.__name__}); run docker compose up -d db")
    cfg = _alembic_config()
    command.downgrade(cfg, "base")
    command.upgrade(cfg, "head")
    yield engine
    engine.dispose()


@pytest.fixture
def db_session(migrated_engine):
    with migrated_engine.begin() as conn:
        conn.execute(text(
            "TRUNCATE ingest_runs, runs, drafts, saved_opportunities, eligibility_verdicts, "
            "solicitation_briefs, chunks, documents, companies, opportunities CASCADE"
        ))
    session = make_session_factory(migrated_engine)()
    yield session
    session.close()
```

```python
# tests/db/test_migrations.py
import pytest
from sqlalchemy import inspect, text

pytestmark = pytest.mark.db

EXPECTED_TABLES = {
    "opportunities", "documents", "chunks", "companies", "solicitation_briefs",
    "eligibility_verdicts", "saved_opportunities", "drafts", "runs", "ingest_runs",
}


def test_all_tables_exist(migrated_engine):
    assert EXPECTED_TABLES <= set(inspect(migrated_engine).get_table_names())


def test_vector_extension_and_indexes(migrated_engine):
    with migrated_engine.connect() as conn:
        assert conn.execute(text("select 1 from pg_extension where extname='vector'")).scalar() == 1
        idx = dict(conn.execute(text(
            "select indexname, indexdef from pg_indexes where tablename='chunks'"
        )).all())
    assert "hnsw" in idx["ix_chunks_embedding_hnsw"]
    assert "vector_cosine_ops" in idx["ix_chunks_embedding_hnsw"]
    assert "gin" in idx["ix_chunks_tsv"]


def test_tsv_is_generated(migrated_engine):
    with migrated_engine.begin() as conn:
        opp = conn.execute(text(
            "insert into opportunities (id, source, source_id, kind, title, agency, summary, url, status, "
            "naics, assistance_listings, eligibility_codes, raw, content_hash) values "
            "(gen_random_uuid(), 't', '1', 'grant', 't', 'a', '', 'u', 'open', '{}', '{}', '{}', '{}', 'h') "
            "returning id")).scalar()
        doc = conn.execute(text(
            "insert into documents (id, opportunity_id, corpus, gcs_uri, title, parse_status, sha256) values "
            "(gen_random_uuid(), :o, 'solicitation', 'file:///x', 'x', 'pending', 's') returning id"),
            {"o": opp}).scalar()
        tsv = conn.execute(text(
            "insert into chunks (id, document_id, ord, section_path, text, n_tokens) values "
            "(gen_random_uuid(), :d, 0, 'Eligibility', 'small business concerns', 3) returning tsv::text"),
            {"d": doc}).scalar()
        conn.execute(text("delete from opportunities"))
    assert "small" in tsv and "elig" in tsv
```

- [ ] **Step 5: Run to see it fail**

Run: `uv run pytest tests/db -v`
Expected: FAIL (Alembic has no revisions, so the tables don't exist).

- [ ] **Step 6: Generate and complete the initial revision**

Run: `uv run alembic revision --autogenerate -m "initial schema" --rev-id 0001`
Rename the file to `db/migrations/versions/0001_initial_schema.py`, then edit it:
1. Add `import pgvector.sqlalchemy` to the imports.
2. Make the first line of `upgrade()`: `op.execute("CREATE EXTENSION IF NOT EXISTS vector")`.
3. Check that the `chunks.tsv` column has `sa.Computed(..., persisted=True)` and that the HNSW and GIN indexes carry `postgresql_using`, `postgresql_with` and `postgresql_ops` exactly as in `db/models.py`. Add them by hand if autogenerate dropped them.
4. Make the last line of `downgrade()`: `op.execute("DROP EXTENSION IF EXISTS vector")`.

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/db -v`
Expected: 3 PASS.

Run: `uv run alembic upgrade head` (against the dev DB `grant_capture`)
Expected: `Running upgrade  -> 0001, initial schema`.

- [ ] **Step 8: Commit**

```bash
git add docker-compose.yml db alembic.ini tests/db
git commit -m "feat(m0): Postgres + pgvector schema with Alembic migrations

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 4: CommonGrants-compatible `Opportunity` model

**Files:**
- Create: `ingest/__init__.py` (empty), `ingest/models.py`
- Test: `tests/unit/test_ingest_models.py`

**Interfaces:**
- Produces: `ingest.models.OppStatus` (StrEnum: `forecasted`, `open`, `closed`, `custom`), `Money`, `OppFunding`, `OppTimeline`, `AttachmentRef`, `Opportunity` (fields below, `.content_hash() -> str`, `.to_commongrants(*, record_id: uuid.UUID, created_at: datetime, last_modified_at: datetime) -> common_grants_sdk.schemas.pydantic.OpportunityBase`), `to_cg_applicant_type(code: str) -> dict`, `infer_kind(*texts: str | None, default: str) -> str`, `parse_date(value: str | None) -> date | None`, `parse_money(value) -> Money | None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_ingest_models.py
import uuid
from datetime import UTC, date, datetime
from decimal import Decimal

from common_grants_sdk.schemas.pydantic import OpportunityBase

from ingest.models import (
    AttachmentRef, Money, Opportunity, OppStatus, OppTimeline, infer_kind, parse_date, parse_money,
)


def _opp(**kw):
    base = dict(source="grants_gov", source_id="abc", kind="grant", title="Grid storage R&D",
                status=OppStatus.open, description="desc", agency="DOE", source_url="https://x/abc")
    base.update(kw)
    return Opportunity(**base)


def test_content_hash_is_stable_and_sensitive():
    a, b = _opp(), _opp()
    assert a.content_hash() == b.content_hash()
    assert len(a.content_hash()) == 64
    assert _opp(title="Changed").content_hash() != a.content_hash()
    assert _opp(attachments=[AttachmentRef(url="https://f/1.pdf", file_name="1.pdf")]).content_hash() != a.content_hash()


def test_commongrants_export_validates_against_official_sdk():
    o = _opp(key_dates=OppTimeline(post_date=date(2026, 9, 1), close_date=date(2026, 11, 3)),
             accepted_applicant_types=["small_businesses", "weird_new_code"])
    rid = uuid.UUID("11111111-1111-1111-1111-111111111111")
    now = datetime(2026, 10, 7, tzinfo=UTC)
    cg = o.to_commongrants(record_id=rid, created_at=now, last_modified_at=now)
    assert isinstance(cg, OpportunityBase)
    d = cg.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert d["id"] == str(rid) and d["title"] == "Grid storage R&D"
    assert d["status"]["value"] == "open"
    assert d["keyDates"]["closeDate"]["eventType"] == "singleDate"
    assert d["keyDates"]["closeDate"]["date"] == "2026-11-03"
    assert d["acceptedApplicantTypes"][0]["value"] == "for_profit_small_business"
    assert d["acceptedApplicantTypes"][1] == {"value": "custom", "customValue": "weird_new_code"}
    assert d["customFields"]["sourceId"]["value"] == "abc"
    assert d["source"] == "https://x/abc"


def test_empty_description_still_exports():
    now = datetime(2026, 10, 7, tzinfo=UTC)
    cg = _opp(description="").to_commongrants(record_id=uuid.uuid4(), created_at=now, last_modified_at=now)
    assert cg.description == "(no description provided)"


def test_infer_kind():
    assert infer_kind("DOE SBIR/STTR FY27 Phase I Release 1", default="grant") == "sbir"
    assert infer_kind("Small Business Technology Transfer (STTR) Phase I", default="grant") == "sttr"
    assert infer_kind("Advanced Battery Materials", None, default="contract") == "contract"


def test_parse_helpers_tolerate_messy_values():
    assert parse_date("2026-11-03") == date(2026, 11, 3)
    assert parse_date("2026-11-03T17:00:00-04:00") == date(2026, 11, 3)
    assert parse_date("11/03/2026") == date(2026, 11, 3)
    assert parse_date("2026-10-06 16:33:21.123-04") == date(2026, 10, 6)  # SAM bulk CSV format
    assert parse_date(None) is None and parse_date("") is None and parse_date("TBD") is None
    assert parse_money(150000) == Money(amount=Decimal("150000"))
    assert parse_money("1,250,000.50") == Money(amount=Decimal("1250000.50"))
    assert parse_money(None) is None and parse_money("N/A") is None and parse_money(0) is None
```

- [ ] **Step 2: Run to see it fail**

Run: `uv run pytest tests/unit/test_ingest_models.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ingest'`.

- [ ] **Step 3: Implement `ingest/models.py`**

```python
"""Source-independent opportunity model, field-compatible with the CommonGrants protocol."""

import hashlib
import json
import re
import uuid
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from enum import StrEnum
from typing import Any, Literal

from common_grants_sdk.schemas.pydantic import OpportunityBase
from pydantic import BaseModel, ConfigDict, Field

Kind = Literal["grant", "sbir", "sttr", "contract"]
Source = Literal["grants_gov", "sam_gov"]


class OppStatus(StrEnum):
    forecasted = "forecasted"
    open = "open"
    closed = "closed"
    custom = "custom"


class Money(BaseModel):
    model_config = ConfigDict(frozen=True)
    amount: Decimal
    currency: str = "USD"


class OppFunding(BaseModel):
    model_config = ConfigDict(frozen=True)
    total_amount_available: Money | None = None
    min_award_amount: Money | None = None
    max_award_amount: Money | None = None
    estimated_award_count: int | None = None
    details: str | None = None


class OppTimeline(BaseModel):
    model_config = ConfigDict(frozen=True)
    post_date: date | None = None
    close_date: date | None = None
    other_dates: dict[str, date] = Field(default_factory=dict)


class AttachmentRef(BaseModel):
    model_config = ConfigDict(frozen=True)
    url: str
    file_name: str
    mime_type: str | None = None
    size_bytes: int | None = None


class Opportunity(BaseModel):
    model_config = ConfigDict(frozen=True)

    source: Source
    source_id: str
    kind: Kind
    title: str
    status: OppStatus
    description: str
    agency: str
    source_url: str
    funding: OppFunding = Field(default_factory=OppFunding)
    key_dates: OppTimeline = Field(default_factory=OppTimeline)
    accepted_applicant_types: list[str] = Field(default_factory=list)
    naics: list[str] = Field(default_factory=list)
    assistance_listings: list[str] = Field(default_factory=list)
    attachments: list[AttachmentRef] = Field(default_factory=list)
    custom_fields: dict[str, Any] = Field(default_factory=dict)

    def content_hash(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def to_commongrants(self, *, record_id: uuid.UUID, created_at: datetime,
                        last_modified_at: datetime) -> OpportunityBase:
        """Export as the official CommonGrants OpportunityBase (validated by the SDK)."""

        def money(m: Money | None) -> dict[str, str] | None:
            return None if m is None else {"amount": str(m.amount), "currency": m.currency}

        def event(name: str, d: date | None) -> dict[str, str] | None:
            return None if d is None else {"name": name, "eventType": "singleDate", "date": d.isoformat()}

        def custom(name: str, value: Any) -> dict[str, Any]:
            kind = ("boolean" if isinstance(value, bool) else "integer" if isinstance(value, int)
                    else "number" if isinstance(value, float) else "array" if isinstance(value, list)
                    else "object" if isinstance(value, dict) else "string")
            return {"name": name, "fieldType": kind, "value": value}

        f, k = self.funding, self.key_dates
        extra = {"sourceSystem": self.source, "sourceId": self.source_id, "kind": self.kind,
                 "agency": self.agency, "naics": list(self.naics),
                 "assistanceListings": list(self.assistance_listings), **self.custom_fields}
        payload = {
            "id": str(record_id),
            "title": self.title,
            "status": {"value": self.status.value},
            "description": self.description or "(no description provided)",
            "funding": {
                "totalAmountAvailable": money(f.total_amount_available),
                "minAwardAmount": money(f.min_award_amount),
                "maxAwardAmount": money(f.max_award_amount),
                "estimatedAwardCount": f.estimated_award_count,
                "details": f.details,
            },
            "keyDates": {
                "postDate": event("Posted", k.post_date),
                "closeDate": event("Close date", k.close_date),
                "otherDates": {n: event(n, d) for n, d in k.other_dates.items()} or None,
            },
            "acceptedApplicantTypes": [to_cg_applicant_type(c) for c in self.accepted_applicant_types],
            "source": self.source_url,
            "customFields": {n: custom(n, v) for n, v in extra.items() if v is not None},
            "createdAt": created_at.isoformat(),
            "lastModifiedAt": last_modified_at.isoformat(),
        }
        return OpportunityBase.model_validate(payload)


# Grants.gov applicant type codes -> CommonGrants ApplicantTypeOptions
_APPLICANT_TYPES = {
    "small_businesses": "for_profit_small_business",
    "for_profit_organizations_other_than_small_businesses": "for_profit_not_small_business",
    "individuals": "individual",
    "nonprofits_non_higher_education_with_501c3": "non_profit_with_501c3",
    "nonprofits_non_higher_education_without_501c3": "nonprofit_without_501c3",
    "public_and_state_institutions_of_higher_education": "higher_education_public",
    "private_institutions_of_higher_education": "higher_education_private",
    "state_governments": "government_state",
    "county_governments": "government_county",
    "city_or_township_governments": "government_municipal",
    "special_district_governments": "government_special_district",
    "independent_school_districts": "school_district_independent",
    "federally_recognized_native_american_tribal_governments": "government_tribal",
    "native_american_tribal_organizations": "organization_tribal_other",
    "unrestricted": "unrestricted",
}


def to_cg_applicant_type(code: str) -> dict[str, str]:
    value = _APPLICANT_TYPES.get(code)
    return {"value": value} if value else {"value": "custom", "customValue": code}


_STTR = re.compile(r"\bSTTR\b|technology transfer", re.IGNORECASE)
_SBIR = re.compile(r"\bSBIR\b|small business innovation research", re.IGNORECASE)


def infer_kind(*texts: str | None, default: Kind) -> Kind:
    joined = " ".join(t for t in texts if t)
    if _SBIR.search(joined):
        return "sbir"
    if _STTR.search(joined):
        return "sttr"
    return default


def parse_date(value: str | None) -> date | None:
    if not value:
        return None
    text = value.strip()
    for parser in (
        lambda s: datetime.fromisoformat(s).date(),
        lambda s: datetime.strptime(s, "%m/%d/%Y").date(),
        lambda s: date.fromisoformat(s[:10]),  # e.g. SAM bulk "2026-10-06 16:33:21.123-04"
    ):
        try:
            return parser(text)
        except ValueError:
            continue
    return None


def parse_money(value: Any) -> Money | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        amount = Decimal(str(value).replace(",", "").replace("$", "").strip())
    except InvalidOperation:
        return None
    if amount <= 0:
        return None
    return Money(amount=amount)
```
(`infer_kind` checks SBIR first, because titles like "SBIR/STTR" are SBIR releases.)

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_ingest_models.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add ingest/__init__.py ingest/models.py tests/unit/test_ingest_models.py
git commit -m "feat(m0): CommonGrants-compatible Opportunity model with stable content hash

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Retrying HTTP client, capped downloader and blob stores

**Files:**
- Create: `ingest/http.py`, `ingest/storage.py`
- Test: `tests/unit/test_http.py`, `tests/unit/test_storage.py`

**Interfaces:**
- Produces:
  - `ingest.http.RetryableHTTPError(Exception)`
  - `ingest.http.build_client(timeout: float = 30.0) -> httpx.Client`
  - `ingest.http.request_json(client, method, url, *, max_attempts=5, wait=<exponential>, **kwargs) -> Any`
  - `ingest.http.download(client, url, *, max_bytes: int) -> bytes | None` (returns `None` when the size is over the cap)
  - `ingest.storage.ALLOWED_MIME_TYPES: frozenset[str]`
  - `ingest.storage.is_allowed_attachment(mime: str | None, file_name: str) -> bool`
  - `ingest.storage.safe_key(source: str, source_id: str, file_name: str) -> str`
  - `ingest.storage.BlobStore` (Protocol: `put(key: str, data: bytes) -> str`, `exists(key: str) -> bool`)
  - `ingest.storage.LocalBlobStore(root: Path)`, `ingest.storage.GCSBlobStore(bucket: str, client=None)`, `ingest.storage.blob_store_from_root(root: str) -> BlobStore`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_http.py
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
        assert request_json(c, "GET", "https://api.test/x", wait=wait_none()) == {"ok": True}
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
        return_value=httpx.Response(200, headers={"content-length": "999999999"}, content=b"x")
    )
    respx.get("https://f.test/sneaky").mock(return_value=httpx.Response(200, content=b"x" * 2048))
    respx.get("https://f.test/ok").mock(return_value=httpx.Response(200, content=b"%PDF-1.7"))
    with build_client() as c:
        assert download(c, "https://f.test/big", max_bytes=1024) is None
        assert download(c, "https://f.test/sneaky", max_bytes=1024) is None
        assert download(c, "https://f.test/ok", max_bytes=1024) == b"%PDF-1.7"
```

```python
# tests/unit/test_storage.py
from pathlib import Path

from ingest.storage import LocalBlobStore, is_allowed_attachment, safe_key


def test_safe_key_blocks_traversal_and_odd_names():
    assert safe_key("grants_gov", "123", "../../etc/passwd") == "raw/grants_gov/123/etc_passwd"
    assert safe_key("sam_gov", "abc", "Résumé (final).PDF") == "raw/sam_gov/abc/R_sum_final_.PDF"
    assert safe_key("sam_gov", "abc", "") == "raw/sam_gov/abc/unnamed"
    assert safe_key("sam_gov", "../x", "a.pdf") == "raw/sam_gov/x/a.pdf"


def test_allowed_attachments():
    assert is_allowed_attachment("application/pdf", "nofo.pdf")
    assert is_allowed_attachment(None, "Section_C.docx")
    assert not is_allowed_attachment("application/zip", "all.zip")
    assert not is_allowed_attachment(None, "budget.xlsx")


def test_local_store_round_trip(tmp_path: Path):
    store = LocalBlobStore(tmp_path)
    key = safe_key("grants_gov", "1", "a.pdf")
    assert not store.exists(key)
    uri = store.put(key, b"data")
    assert store.exists(key)
    assert uri.startswith("file:")
    assert (tmp_path / key).read_bytes() == b"data"
```

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/unit/test_http.py tests/unit/test_storage.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement `ingest/http.py`**

```python
"""HTTP helpers: retrying JSON requests and size-capped downloads."""

from typing import Any

import httpx
from tenacity import Retrying, retry_if_exception_type, stop_after_attempt, wait_exponential
from tenacity.wait import wait_base

RETRYABLE_STATUS = frozenset({429, 500, 502, 503, 504})
USER_AGENT = "grant-capture-agent/0.1 (+https://github.com/kb2326/grant-capture-agent)"


class RetryableHTTPError(Exception):
    pass


def build_client(timeout: float = 30.0) -> httpx.Client:
    return httpx.Client(timeout=timeout, headers={"User-Agent": USER_AGENT}, follow_redirects=True)


def request_json(
    client: httpx.Client,
    method: str,
    url: str,
    *,
    max_attempts: int = 5,
    wait: wait_base = wait_exponential(multiplier=0.5, max=20),
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
```

- [ ] **Step 4: Implement `ingest/storage.py`**

```python
"""Blob storage for raw attachments: local filesystem or Google Cloud Storage."""

import re
from pathlib import Path, PurePosixPath
from typing import Protocol

ALLOWED_MIME_TYPES = frozenset({
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/html",
    "text/plain",
})
_ALLOWED_SUFFIXES = frozenset({".pdf", ".docx", ".doc", ".html", ".htm", ".txt"})
_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def is_allowed_attachment(mime: str | None, file_name: str) -> bool:
    if mime:
        return mime.split(";")[0].strip().lower() in ALLOWED_MIME_TYPES
    return PurePosixPath(file_name.lower()).suffix in _ALLOWED_SUFFIXES


def _clean(part: str) -> str:
    name = PurePosixPath(part.replace("\\", "/")).name if "/" in part or "\\" in part else part
    cleaned = _UNSAFE.sub("_", name).strip("._")
    return cleaned or "unnamed"


def safe_key(source: str, source_id: str, file_name: str) -> str:
    segments = [s for s in file_name.replace("\\", "/").split("/") if s not in ("", ".", "..")]
    name = _clean("_".join(segments)) if segments else "unnamed"
    return f"raw/{_clean(source)}/{_clean(source_id)}/{name}"


class BlobStore(Protocol):
    def put(self, key: str, data: bytes) -> str: ...
    def exists(self, key: str) -> bool: ...


class LocalBlobStore:
    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents:
            raise ValueError(f"key escapes blob root: {key}")
        return path

    def put(self, key: str, data: bytes) -> str:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path.as_uri()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()


class GCSBlobStore:
    def __init__(self, bucket: str, client=None) -> None:
        from google.cloud import storage

        self._client = client or storage.Client()
        self._bucket = self._client.bucket(bucket)
        self.bucket_name = bucket

    def put(self, key: str, data: bytes) -> str:
        self._bucket.blob(key).upload_from_string(data)
        return f"gs://{self.bucket_name}/{key}"

    def exists(self, key: str) -> bool:
        return self._bucket.blob(key).exists()


def blob_store_from_root(root: str) -> BlobStore:
    if root.startswith("gs://"):
        return GCSBlobStore(root.removeprefix("gs://").split("/", 1)[0])
    return LocalBlobStore(Path(root))
```

Check the expected `safe_key` values by hand. For `../../etc/passwd`, the segments are `["etc", "passwd"]`, giving `"etc_passwd"`. For `Résumé (final).PDF`, the `é` and the `" ("` run each become `_`, and the trailing `)` becomes `_` before `.PDF`, giving `R_sum_final_.PDF`. If your output differs only in how characters inside the name are replaced, fix the implementation, not the test: the test pins the behaviour.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_http.py tests/unit/test_storage.py -v`
Expected: 6 PASS.

- [ ] **Step 6: Commit**

```bash
git add ingest/http.py ingest/storage.py tests/unit/test_http.py tests/unit/test_storage.py
git commit -m "feat(m0): retrying HTTP client, capped downloads and safe blob storage

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 6: Grants.gov (Simpler Grants) adapter

**Files:**
- Create: `ingest/sources/__init__.py` (empty), `ingest/sources/base.py`, `ingest/sources/grants_gov.py`, `tests/fixtures/grants_gov/search_page1.json`, `tests/fixtures/grants_gov/detail_full.json`, `tests/fixtures/grants_gov/detail_sparse.json`
- Test: `tests/unit/test_grants_gov.py`

**Interfaces:**
- Consumes: `request_json`, `Opportunity`, `parse_date`, `parse_money`, `infer_kind`.
- Produces:
  - `ingest.sources.base.SourceAdapter` (Protocol: attribute `name: str`, method `iter_opportunities(limit: int | None = None) -> Iterator[Opportunity]`)
  - `ingest.sources.grants_gov.GRANTS_BASE = "https://api.simpler.grants.gov"`
  - `ingest.sources.grants_gov.map_grants_gov(detail: dict) -> Opportunity`
  - `ingest.sources.grants_gov.GrantsGovAdapter(client: httpx.Client, api_key: str, page_size: int = 100)`

- [ ] **Step 1: Create fixtures matching the published OpenAPI schemas** (`OpportunityV1Schema`, `OpportunitySummaryV1Schema`, `OpportunityAttachmentV1Schema`, `PaginationInfoSchema`)

```json
// tests/fixtures/grants_gov/search_page1.json
{
  "status_code": 200, "message": "Success",
  "pagination_info": {"page_offset": 1, "page_size": 2, "total_pages": 1, "total_records": 2,
                      "sort_order": [{"order_by": "post_date", "sort_direction": "descending"}]},
  "data": [
    {"opportunity_id": "11111111-1111-1111-1111-111111111111", "opportunity_title": "DOE SBIR/STTR FY27 Phase I Release 1"},
    {"opportunity_id": "22222222-2222-2222-2222-222222222222", "opportunity_title": "Forecast: Grid Modernization Lab Call"}
  ],
  "facet_counts": {}
}
```

```json
// tests/fixtures/grants_gov/detail_full.json
{
  "status_code": 200, "message": "Success",
  "data": {
    "opportunity_id": "11111111-1111-1111-1111-111111111111",
    "legacy_opportunity_id": 360001,
    "opportunity_number": "DE-FOA-0003500",
    "opportunity_title": "DOE SBIR/STTR FY27 Phase I Release 1",
    "opportunity_status": "posted",
    "agency_code": "DOE-SC", "agency_name": "Office of Science", "top_level_agency_name": "Department of Energy",
    "category": "discretionary",
    "opportunity_assistance_listings": [{"assistance_listing_number": "81.049", "program_title": "Office of Science Financial Assistance Program"}],
    "summary": {
      "summary_description": "<p>Phase I awards for small businesses in energy storage.</p>",
      "applicant_eligibility_description": "Only small business concerns as defined by SBA are eligible.",
      "applicant_types": ["small_businesses"],
      "funding_instruments": ["grant"],
      "is_cost_sharing": false, "is_forecast": false,
      "post_date": "2026-09-15", "close_date": "2026-11-03",
      "award_floor": 50000, "award_ceiling": 200000,
      "estimated_total_program_funding": 30000000, "expected_number_of_awards": 150
    },
    "attachments": [
      {"opportunity_attachment_id": "a1", "file_name": "DE-FOA-0003500.pdf", "mime_type": "application/pdf",
       "file_size_bytes": 2048000, "download_path": "https://files.simpler.grants.gov/a1/DE-FOA-0003500.pdf",
       "file_description": "FOA", "created_at": "2026-09-15T12:00:00+00:00", "updated_at": "2026-09-15T12:00:00+00:00"},
      {"opportunity_attachment_id": "a2", "file_name": "budget.xlsx",
       "mime_type": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
       "file_size_bytes": 10000, "download_path": "https://files.simpler.grants.gov/a2/budget.xlsx",
       "file_description": "Budget template", "created_at": "2026-09-15T12:00:00+00:00", "updated_at": "2026-09-15T12:00:00+00:00"}
    ]
  }
}
```

```json
// tests/fixtures/grants_gov/detail_sparse.json
{
  "status_code": 200, "message": "Success",
  "data": {
    "opportunity_id": "22222222-2222-2222-2222-222222222222",
    "opportunity_number": null,
    "opportunity_title": "Forecast: Grid Modernization Lab Call",
    "opportunity_status": "forecasted",
    "agency_code": null, "agency_name": null, "top_level_agency_name": "Department of Energy",
    "opportunity_assistance_listings": null,
    "summary": {"is_forecast": true, "forecasted_post_date": "2026-12-01", "forecasted_close_date": null,
                "summary_description": null, "applicant_types": null, "award_ceiling": null, "award_floor": null},
    "attachments": null
  }
}
```

(Remove the `// path` comment lines when saving; JSON has no comments.)

- [ ] **Step 2: Write the failing tests**

```python
# tests/unit/test_grants_gov.py
import json
from datetime import date
from decimal import Decimal
from pathlib import Path

import httpx
import respx

from ingest.http import build_client
from ingest.models import OppStatus
from ingest.sources.grants_gov import GRANTS_BASE, GrantsGovAdapter, map_grants_gov

FIX = Path("tests/fixtures/grants_gov")


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_map_full_record():
    o = map_grants_gov(load("detail_full.json")["data"])
    assert o.source == "grants_gov" and o.source_id == "11111111-1111-1111-1111-111111111111"
    assert o.kind == "sbir" and o.status is OppStatus.open
    assert o.agency == "Department of Energy / Office of Science"
    assert o.key_dates.post_date == date(2026, 9, 15) and o.key_dates.close_date == date(2026, 11, 3)
    assert o.funding.max_award_amount.amount == Decimal("200000")
    assert o.funding.estimated_award_count == 150
    assert o.accepted_applicant_types == ["small_businesses"]
    assert o.assistance_listings == ["81.049"]
    assert [a.file_name for a in o.attachments] == ["DE-FOA-0003500.pdf", "budget.xlsx"]
    assert o.custom_fields["opportunity_number"] == "DE-FOA-0003500"
    assert "small business concerns" in o.custom_fields["applicant_eligibility_description"]
    assert o.source_url == "https://simpler.grants.gov/opportunity/11111111-1111-1111-1111-111111111111"


def test_map_sparse_forecast_record():
    o = map_grants_gov(load("detail_sparse.json")["data"])
    assert o.status is OppStatus.forecasted
    assert o.kind == "grant"
    assert o.agency == "Department of Energy"
    assert o.key_dates.post_date == date(2026, 12, 1) and o.key_dates.close_date is None
    assert o.description == "" and o.attachments == [] and o.assistance_listings == []
    assert o.funding.max_award_amount is None


@respx.mock
def test_adapter_pages_and_fetches_details():
    search = respx.post(f"{GRANTS_BASE}/v1/opportunities/search").mock(
        return_value=httpx.Response(200, json=load("search_page1.json")))
    respx.get(f"{GRANTS_BASE}/v1/opportunities/11111111-1111-1111-1111-111111111111").mock(
        return_value=httpx.Response(200, json=load("detail_full.json")))
    respx.get(f"{GRANTS_BASE}/v1/opportunities/22222222-2222-2222-2222-222222222222").mock(
        return_value=httpx.Response(200, json=load("detail_sparse.json")))
    with build_client() as c:
        opps = list(GrantsGovAdapter(c, api_key="k", page_size=2, min_interval_s=0).iter_opportunities())
    assert [o.source_id[:4] for o in opps] == ["1111", "2222"]
    sent = json.loads(search.calls[0].request.content)
    assert sent["filters"]["opportunity_status"]["one_of"] == ["posted", "forecasted"]
    assert search.calls[0].request.headers["X-API-Key"] == "k"


@respx.mock
def test_adapter_respects_limit():
    respx.post(f"{GRANTS_BASE}/v1/opportunities/search").mock(
        return_value=httpx.Response(200, json=load("search_page1.json")))
    detail = respx.get(url__startswith=f"{GRANTS_BASE}/v1/opportunities/").mock(
        return_value=httpx.Response(200, json=load("detail_full.json")))
    with build_client() as c:
        opps = list(GrantsGovAdapter(c, api_key="k", min_interval_s=0).iter_opportunities(limit=1))
    assert len(opps) == 1 and detail.call_count == 1


@respx.mock
def test_adapter_throttles_to_rate_limit():
    respx.post(f"{GRANTS_BASE}/v1/opportunities/search").mock(
        return_value=httpx.Response(200, json=load("search_page1.json")))
    respx.get(url__startswith=f"{GRANTS_BASE}/v1/opportunities/").mock(
        return_value=httpx.Response(200, json=load("detail_full.json")))
    sleeps: list[float] = []
    with build_client() as c:
        adapter = GrantsGovAdapter(c, api_key="k", page_size=2, min_interval_s=1.1,
                                   sleep=sleeps.append, clock=lambda: 0.0)
        list(adapter.iter_opportunities())
    assert sleeps == [1.1, 1.1]  # 3 requests (1 search + 2 details) → 2 waits
```

- [ ] **Step 3: Run to see them fail**

Run: `uv run pytest tests/unit/test_grants_gov.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement**

```python
# ingest/sources/base.py
from collections.abc import Iterator
from typing import Protocol

from ingest.models import Opportunity


class SourceAdapter(Protocol):
    name: str

    def iter_opportunities(self, limit: int | None = None) -> Iterator[Opportunity]: ...
```

```python
# ingest/sources/grants_gov.py
"""Grants.gov via the Simpler Grants API (https://api.simpler.grants.gov)."""

import time
from collections.abc import Iterator
from typing import Any

import httpx

from ingest.http import request_json
from ingest.models import (
    AttachmentRef, Opportunity, OppFunding, OppStatus, OppTimeline, infer_kind, parse_date, parse_money,
)

GRANTS_BASE = "https://api.simpler.grants.gov"
_STATUS = {"posted": OppStatus.open, "forecasted": OppStatus.forecasted,
           "closed": OppStatus.closed, "archived": OppStatus.closed}


def map_grants_gov(d: dict[str, Any]) -> Opportunity:
    s = d.get("summary") or {}
    forecast = bool(s.get("is_forecast"))
    names = [n for n in (d.get("top_level_agency_name"), d.get("agency_name")) if n]
    agency = " / ".join(dict.fromkeys(names)) or "Unknown agency"
    estimated = s.get("expected_number_of_awards")
    return Opportunity(
        source="grants_gov",
        source_id=str(d["opportunity_id"]),
        kind=infer_kind(d.get("opportunity_title"), d.get("opportunity_number"), default="grant"),
        title=d.get("opportunity_title") or "(untitled)",
        status=_STATUS.get(d.get("opportunity_status") or "", OppStatus.custom),
        description=s.get("summary_description") or "",
        agency=agency,
        source_url=f"https://simpler.grants.gov/opportunity/{d['opportunity_id']}",
        funding=OppFunding(
            total_amount_available=parse_money(s.get("estimated_total_program_funding")),
            min_award_amount=parse_money(s.get("award_floor")),
            max_award_amount=parse_money(s.get("award_ceiling")),
            estimated_award_count=estimated if isinstance(estimated, int) else None,
        ),
        key_dates=OppTimeline(
            post_date=parse_date(s.get("forecasted_post_date") if forecast else s.get("post_date")),
            close_date=parse_date(s.get("forecasted_close_date") if forecast else s.get("close_date")),
        ),
        accepted_applicant_types=list(s.get("applicant_types") or []),
        assistance_listings=[a["assistance_listing_number"]
                             for a in (d.get("opportunity_assistance_listings") or [])
                             if a.get("assistance_listing_number")],
        attachments=[AttachmentRef(url=a["download_path"], file_name=a.get("file_name") or "",
                                   mime_type=a.get("mime_type"), size_bytes=a.get("file_size_bytes"))
                     for a in (d.get("attachments") or []) if a.get("download_path")],
        custom_fields={
            "opportunity_number": d.get("opportunity_number"),
            "agency_code": d.get("agency_code"),
            "funding_instruments": list(s.get("funding_instruments") or []),
            "is_cost_sharing": s.get("is_cost_sharing"),
            "applicant_eligibility_description": s.get("applicant_eligibility_description"),
        },
    )


class GrantsGovAdapter:
    name = "grants_gov"

    def __init__(self, client: httpx.Client, api_key: str, page_size: int = 100,
                 min_interval_s: float = 1.1, sleep=time.sleep, clock=time.monotonic) -> None:
        self.client, self.page_size = client, page_size
        self.headers = {"X-API-Key": api_key, "Content-Type": "application/json"}
        self.min_interval_s, self._sleep, self._clock = min_interval_s, sleep, clock
        self._last: float | None = None

    def _call(self, method: str, url: str, **kwargs):
        # Simpler Grants allows 60 requests/minute per key; stay just under it.
        if self._last is not None:
            wait = self.min_interval_s - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        self._last = self._clock()
        return request_json(self.client, method, url, headers=self.headers, **kwargs)

    def iter_opportunities(self, limit: int | None = None) -> Iterator[Opportunity]:
        page, yielded = 1, 0
        while True:
            body = {
                "filters": {"opportunity_status": {"one_of": ["posted", "forecasted"]}},
                "pagination": {"page_offset": page, "page_size": self.page_size,
                               "sort_order": [{"order_by": "post_date", "sort_direction": "descending"}]},
            }
            payload = self._call("POST", f"{GRANTS_BASE}/v1/opportunities/search", json=body)
            for item in payload.get("data") or []:
                detail = self._call("GET", f"{GRANTS_BASE}/v1/opportunities/{item['opportunity_id']}")
                yield map_grants_gov(detail["data"])
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
            if page >= (payload.get("pagination_info") or {}).get("total_pages", page):
                return
            page += 1
```

`dict.fromkeys` drops a duplicate when the agency and sub-agency names are the same.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_grants_gov.py -v`
Expected: 5 PASS.

- [ ] **Step 6: Live check (needs `SIMPLER_GRANTS_API_KEY` in `.env`)**

Run:
```bash
uv run python -c "
from app.config import get_settings; from ingest.http import build_client
from ingest.sources.grants_gov import GrantsGovAdapter
s=get_settings()
with build_client() as c:
    for o in GrantsGovAdapter(c, s.simpler_grants_api_key.get_secret_value(), page_size=3).iter_opportunities(limit=3):
        print(o.kind, o.status, o.key_dates.close_date, len(o.attachments), o.title[:60])"
```
Expected: 3 lines of real opportunities. If a field mapping is wrong (for example, attachments are always 0 while the website shows files), save that live detail response as `tests/fixtures/grants_gov/detail_live.json`, add a test for it, and fix the mapper.

- [ ] **Step 7: Commit**

```bash
git add ingest/sources tests/fixtures/grants_gov tests/unit/test_grants_gov.py
git commit -m "feat(m0): Grants.gov (Simpler Grants API) adapter

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: SAM.gov API adapter with a hard daily request budget (on-demand use)

**Files:**
- Create: `ingest/sources/sam_gov.py`, `tests/fixtures/sam_gov/search_o_541715.json`
- Test: `tests/unit/test_sam_gov.py`

**Interfaces:**
- Consumes: `request_json`, `Opportunity`, helpers from Task 4.
- Produces:
  - `ingest.sources.sam_gov.SAM_URL = "https://api.sam.gov/opportunities/v2/search"`
  - `R_AND_D_NAICS = ("541713", "541714", "541715")`, `NOTICE_TYPES = ("o", "p", "k")`
  - `map_sam_gov(record: dict) -> Opportunity`
  - `SamGovAdapter(client, api_key: str, *, request_budget: int, today: date | None = None, page_size: int = 1000)` with attribute `requests_made: int` and `budget_exhausted: bool`

- [ ] **Step 1: Fixture** (fields from the SAM.gov Get Opportunities v2 response)

```json
{
  "totalRecords": 2, "limit": 1000, "offset": 0,
  "opportunitiesData": [
    {"noticeId": "n-001", "title": "SBIR Phase I: Solid-State Grid Battery Management",
     "solicitationNumber": "W911NF-27-S-0001", "fullParentPathName": "DEPT OF DEFENSE.DEPT OF THE ARMY.ARL",
     "postedDate": "2026-09-20", "type": "Solicitation", "baseType": "Solicitation",
     "typeOfSetAside": "SBA", "typeOfSetAsideDescription": "Total Small Business Set-Aside (FAR 19.5)",
     "responseDeadLine": "2026-11-15T17:00:00-05:00", "naicsCode": "541715", "classificationCode": "AJ12",
     "active": "Yes", "description": "https://api.sam.gov/prod/opportunities/v1/noticedesc?noticeid=n-001",
     "uiLink": "https://sam.gov/opp/n-001/view",
     "resourceLinks": ["https://sam.gov/api/prod/opps/v3/opportunities/resources/files/f1/download"]},
    {"noticeId": "n-002", "title": "Sources Sought for Power Electronics Testing",
     "solicitationNumber": null, "fullParentPathName": "NATIONAL AERONAUTICS AND SPACE ADMINISTRATION",
     "postedDate": "2026-09-18", "type": "Presolicitation", "baseType": "Presolicitation",
     "typeOfSetAside": null, "responseDeadLine": null, "naicsCode": "541715",
     "active": "Yes", "description": null, "uiLink": "https://sam.gov/opp/n-002/view", "resourceLinks": null}
  ]
}
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/unit/test_sam_gov.py
import json
from datetime import date
from pathlib import Path

import httpx
import respx

from ingest.http import build_client
from ingest.models import OppStatus
from ingest.sources.sam_gov import SAM_URL, SamGovAdapter, map_sam_gov

FIX = json.loads(Path("tests/fixtures/sam_gov/search_o_541715.json").read_text(encoding="utf-8"))


def test_map_records_including_nulls_and_timezones():
    a = map_sam_gov(FIX["opportunitiesData"][0])
    assert a.source == "sam_gov" and a.source_id == "n-001" and a.kind == "sbir"
    assert a.status is OppStatus.open
    assert a.key_dates.close_date == date(2026, 11, 15)
    assert a.agency == "DEPT OF DEFENSE > DEPT OF THE ARMY > ARL"
    assert a.naics == ["541715"]
    assert a.attachments[0].file_name == "f1"
    assert a.custom_fields["set_aside"] == "SBA"
    assert a.custom_fields["description_url"].endswith("noticeid=n-001")
    b = map_sam_gov(FIX["opportunitiesData"][1])
    assert b.kind == "contract" and b.key_dates.close_date is None and b.attachments == []
    assert b.description == ""


@respx.mock
def test_budget_is_never_exceeded():
    route = respx.get(SAM_URL).mock(return_value=httpx.Response(200, json=FIX))
    with build_client() as c:
        adapter = SamGovAdapter(c, "key", request_budget=2, today=date(2026, 10, 7))
        opps = list(adapter.iter_opportunities())
    assert route.call_count == 2
    assert adapter.requests_made == 2 and adapter.budget_exhausted
    assert len({o.source_id for o in opps}) == len(opps)  # deduplicated across query combos


@respx.mock
def test_query_parameters():
    route = respx.get(SAM_URL).mock(return_value=httpx.Response(200, json={"totalRecords": 0, "opportunitiesData": []}))
    with build_client() as c:
        list(SamGovAdapter(c, "key", request_budget=1, today=date(2026, 10, 7)).iter_opportunities())
    params = dict(route.calls[0].request.url.params)
    assert params["api_key"] == "key" and params["ptype"] == "o" and params["ncode"] == "541713"
    assert params["postedFrom"] == "10/08/2025" and params["postedTo"] == "10/07/2026"
    assert params["limit"] == "1000" and params["offset"] == "0"
```

- [ ] **Step 3: Run to see them fail**

Run: `uv run pytest tests/unit/test_sam_gov.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement**

```python
# ingest/sources/sam_gov.py
"""SAM.gov Get Opportunities API v2. Public keys allow ~10 requests/day, so every call is budgeted."""

import logging
from collections.abc import Iterator
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlparse

import httpx

from ingest.http import request_json
from ingest.models import AttachmentRef, Opportunity, OppStatus, OppTimeline, infer_kind, parse_date

log = logging.getLogger(__name__)

SAM_URL = "https://api.sam.gov/opportunities/v2/search"
R_AND_D_NAICS = ("541713", "541714", "541715")
NOTICE_TYPES = ("o", "p", "k")


def _file_name(url: str) -> str:
    parts = [p for p in urlparse(url).path.split("/") if p]
    if parts and parts[-1] == "download" and len(parts) >= 2:
        return parts[-2]
    return parts[-1] if parts else "attachment"


def map_sam_gov(r: dict[str, Any]) -> Opportunity:
    links = r.get("resourceLinks") or []
    return Opportunity(
        source="sam_gov",
        source_id=str(r["noticeId"]),
        kind=infer_kind(r.get("title"), r.get("solicitationNumber"), default="contract"),
        title=r.get("title") or "(untitled)",
        status=OppStatus.open if (r.get("active") or "").lower() == "yes" else OppStatus.closed,
        description="",  # SAM returns a URL that costs one request per notice; fetched on demand in M1
        agency=" > ".join(p for p in (r.get("fullParentPathName") or "Unknown agency").split(".") if p),
        source_url=r.get("uiLink") or f"https://sam.gov/opp/{r['noticeId']}/view",
        key_dates=OppTimeline(post_date=parse_date(r.get("postedDate")),
                              close_date=parse_date(r.get("responseDeadLine"))),
        naics=[r["naicsCode"]] if r.get("naicsCode") else [],
        attachments=[AttachmentRef(url=u, file_name=_file_name(u)) for u in links],
        custom_fields={
            "solicitation_number": r.get("solicitationNumber"),
            "notice_type": r.get("type"),
            "set_aside": r.get("typeOfSetAside"),
            "set_aside_description": r.get("typeOfSetAsideDescription"),
            "classification_code": r.get("classificationCode"),
            "description_url": r.get("description"),
        },
    )


class SamGovAdapter:
    name = "sam_gov_api"

    def __init__(self, client: httpx.Client, api_key: str, *, request_budget: int,
                 today: date | None = None, page_size: int = 1000) -> None:
        self.client, self.api_key, self.page_size = client, api_key, page_size
        self.request_budget, self.today = request_budget, today or date.today()
        self.requests_made, self.budget_exhausted = 0, False

    def _search(self, ptype: str, naics: str, offset: int) -> dict[str, Any] | None:
        if self.requests_made >= self.request_budget:
            if not self.budget_exhausted:
                log.warning("SAM.gov request budget (%d) reached; stopping", self.request_budget)
            self.budget_exhausted = True
            return None
        self.requests_made += 1
        params = {
            "api_key": self.api_key, "ptype": ptype, "ncode": naics,
            "postedFrom": (self.today - timedelta(days=364)).strftime("%m/%d/%Y"),
            "postedTo": self.today.strftime("%m/%d/%Y"),
            "limit": str(self.page_size), "offset": str(offset),
        }
        return request_json(self.client, "GET", SAM_URL, params=params, max_attempts=2)

    def iter_opportunities(self, limit: int | None = None) -> Iterator[Opportunity]:
        seen: set[str] = set()
        for ptype in NOTICE_TYPES:
            for naics in R_AND_D_NAICS:
                offset = 0
                while True:
                    payload = self._search(ptype, naics, offset)
                    if payload is None:
                        return
                    records = payload.get("opportunitiesData") or []
                    for r in records:
                        if r.get("noticeId") in seen:
                            continue
                        seen.add(r["noticeId"])
                        yield map_sam_gov(r)
                        if limit is not None and len(seen) >= limit:
                            return
                    if offset + len(records) >= int(payload.get("totalRecords") or 0) or not records:
                        break
                    offset += len(records)
```
`max_attempts=2` keeps retries from burning the quota. The `offset` advances by record count. If the live check (Step 6) shows that SAM treats `offset` as a page index, change only the last line to `offset += 1` and update the test expectations.

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_sam_gov.py -v`
Expected: 3 PASS. (In `test_budget_is_never_exceeded`, the fixture returns the same 2 records for every query, so the dedupe assertion pins cross-query de-duplication.)

- [ ] **Step 6: Live check (needs `SAM_API_KEY`; uses 1 request of the day's quota)**

```bash
uv run python -c "
from app.config import get_settings; from ingest.http import build_client
from ingest.sources.sam_gov import SamGovAdapter
s=get_settings()
with build_client() as c:
    a=SamGovAdapter(c, s.sam_api_key.get_secret_value(), request_budget=1)
    opps=list(a.iter_opportunities())
    print(len(opps), a.requests_made, [o.title[:50] for o in opps[:3]])"
```
Expected: `requests_made` is 1, and up to 1000 real notices are printed.

- [ ] **Step 7: Commit**

```bash
git add ingest/sources/sam_gov.py tests/fixtures/sam_gov tests/unit/test_sam_gov.py
git commit -m "feat(m0): SAM.gov adapter with hard daily request budget

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7b: SAM.gov daily bulk extract adapter (primary SAM source)

**Files:**
- Create: `ingest/sources/sam_gov_bulk.py`, `tests/fixtures/sam_gov/bulk_sample.csv`
- Modify: `.gitignore` (add `data/cache/`)
- Test: `tests/unit/test_sam_gov_bulk.py`

**Interfaces:**
- Consumes: `httpx.Client`, `Opportunity` and the helpers from Task 4, `R_AND_D_NAICS` from Task 7.
- Produces:
  - `ingest.sources.sam_gov_bulk.SAM_BULK_URL`
  - `map_sam_csv_row(row: dict[str, str]) -> Opportunity`
  - `SamBulkAdapter(client, *, cache_path: Path, url: str = SAM_BULK_URL, max_age_hours: float = 20, naics: tuple[str, ...] = R_AND_D_NAICS)`, `name = "sam_gov"`

Why: SAM.gov publishes every notice as one public CSV each day. It's about 210 MB, needs no key, has no quota, and **includes the full description text**. For bulk loading that beats the 10-requests/day API. The API (Task 7) stays for fetching a single notice's attachment links on demand.

- [ ] **Step 1: Fixture** (`tests/fixtures/sam_gov/bulk_sample.csv`; the column names are the real extract headers, trimmed to the ones we read plus two we ignore)

```csv
"NoticeId","Title","Sol#","Department/Ind.Agency","Sub-Tier","Office","PostedDate","Type","BaseType","SetASideCode","ResponseDeadLine","NaicsCode","Active","Link","Description","PopCity","Awardee"
"n-101","SBIR Phase I: Grid-Forming Inverter Controls","W911NF-27-S-0101","DEPT OF DEFENSE","DEPT OF THE ARMY","ARL","2026-10-01 09:12:00.000-04","Solicitation","Solicitation","SBA","2026-11-20T17:00:00-05:00","541715","Yes","https://sam.gov/opp/n-101/view","Seeking grid-forming inverter control research.","Adelphi",""
"n-102","Janitorial Services","FA001-27-Q-0001","DEPT OF DEFENSE","DEPT OF THE AIR FORCE","","2026-10-02 10:00:00.000-04","Solicitation","Solicitation","","2026-10-30","561720","Yes","https://sam.gov/opp/n-102/view","Clean buildings.","",""
"n-103","Battery Test Services","","NATIONAL AERONAUTICS AND SPACE ADMINISTRATION","","","2026-09-29 08:00:00.000-04","Award Notice","Award Notice","","","541715","Yes","https://sam.gov/opp/n-103/view","Award.","","Acme"
"n-104","Power Electronics Sources Sought","","DEPT OF ENERGY","","","2026-09-28 08:00:00.000-04","Presolicitation","Presolicitation","","","541714","No","https://sam.gov/opp/n-104/view","","",""
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/unit/test_sam_gov_bulk.py
import os
import time
from datetime import date
from pathlib import Path

import httpx
import respx

from ingest.http import build_client
from ingest.models import OppStatus
from ingest.sources.sam_gov_bulk import SAM_BULK_URL, SamBulkAdapter, map_sam_csv_row

SAMPLE = Path("tests/fixtures/sam_gov/bulk_sample.csv").read_bytes()


def test_map_row():
    row = {"NoticeId": "n-101", "Title": "SBIR Phase I: Grid-Forming Inverter Controls", "Sol#": "W911",
           "Department/Ind.Agency": "DEPT OF DEFENSE", "Sub-Tier": "DEPT OF THE ARMY", "Office": "ARL",
           "PostedDate": "2026-10-01 09:12:00.000-04", "Type": "Solicitation", "BaseType": "Solicitation",
           "SetASideCode": "SBA", "ResponseDeadLine": "2026-11-20T17:00:00-05:00", "NaicsCode": "541715",
           "Active": "Yes", "Link": "https://sam.gov/opp/n-101/view", "Description": "Seeking research."}
    o = map_sam_csv_row(row)
    assert o.source == "sam_gov" and o.kind == "sbir" and o.status is OppStatus.open
    assert o.agency == "DEPT OF DEFENSE > DEPT OF THE ARMY > ARL"
    assert o.key_dates.post_date == date(2026, 10, 1) and o.key_dates.close_date == date(2026, 11, 20)
    assert o.description == "Seeking research." and o.attachments == []
    assert o.custom_fields["set_aside"] == "SBA"


@respx.mock
def test_filters_to_rd_naics_and_notice_types(tmp_path: Path):
    respx.get(SAM_BULK_URL).mock(return_value=httpx.Response(200, content=SAMPLE))
    with build_client() as c:
        opps = list(SamBulkAdapter(c, cache_path=tmp_path / "sam.csv").iter_opportunities())
    # n-102: wrong NAICS; n-103: award notice; n-104 kept although inactive (status closed)
    assert [o.source_id for o in opps] == ["n-101", "n-104"]
    assert opps[1].status is OppStatus.closed


@respx.mock
def test_fresh_cache_skips_download_and_stale_cache_refreshes(tmp_path: Path):
    cache = tmp_path / "sam.csv"
    cache.write_bytes(SAMPLE)
    route = respx.get(SAM_BULK_URL).mock(return_value=httpx.Response(200, content=SAMPLE))
    with build_client() as c:
        assert len(list(SamBulkAdapter(c, cache_path=cache).iter_opportunities())) == 2
    assert route.call_count == 0
    old = time.time() - 30 * 3600
    os.utime(cache, (old, old))
    with build_client() as c:
        list(SamBulkAdapter(c, cache_path=cache).iter_opportunities())
    assert route.call_count == 1
```

- [ ] **Step 3: Run to see them fail**

Run: `uv run pytest tests/unit/test_sam_gov_bulk.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 4: Implement**

```python
# ingest/sources/sam_gov_bulk.py
"""SAM.gov Contract Opportunities daily public extract (no key, no quota, includes descriptions)."""

import csv
import time
from collections.abc import Iterator
from pathlib import Path

import httpx

from ingest.models import Opportunity, OppStatus, OppTimeline, infer_kind, parse_date
from ingest.sources.sam_gov import R_AND_D_NAICS

csv.field_size_limit(10_000_000)  # descriptions can be very long

SAM_BULK_URL = ("https://s3.amazonaws.com/falextracts/Contract%20Opportunities/datagov/"
                "ContractOpportunitiesFullCSV.csv")
BASE_TYPES = frozenset({"Solicitation", "Presolicitation", "Combined Synopsis/Solicitation"})


def _get(r: dict[str, str], key: str) -> str:
    return (r.get(key) or "").strip()


def map_sam_csv_row(r: dict[str, str]) -> Opportunity:
    notice_id = _get(r, "NoticeId")
    agency_parts = [_get(r, k) for k in ("Department/Ind.Agency", "Sub-Tier", "Office")]
    return Opportunity(
        source="sam_gov",
        source_id=notice_id,
        kind=infer_kind(_get(r, "Title"), _get(r, "Sol#"), default="contract"),
        title=_get(r, "Title") or "(untitled)",
        status=OppStatus.open if _get(r, "Active").lower() == "yes" else OppStatus.closed,
        description=_get(r, "Description"),
        agency=" > ".join(p for p in agency_parts if p) or "Unknown agency",
        source_url=_get(r, "Link") or f"https://sam.gov/opp/{notice_id}/view",
        key_dates=OppTimeline(post_date=parse_date(_get(r, "PostedDate")),
                              close_date=parse_date(_get(r, "ResponseDeadLine"))),
        naics=[_get(r, "NaicsCode")] if _get(r, "NaicsCode") else [],
        custom_fields={
            "solicitation_number": _get(r, "Sol#") or None,
            "notice_type": _get(r, "Type") or None,
            "set_aside": _get(r, "SetASideCode") or None,
        },
    )


class SamBulkAdapter:
    name = "sam_gov"

    def __init__(self, client: httpx.Client, *, cache_path: Path, url: str = SAM_BULK_URL,
                 max_age_hours: float = 20, naics: tuple[str, ...] = R_AND_D_NAICS) -> None:
        self.client, self.cache_path, self.url = client, cache_path, url
        self.max_age_s, self.naics = max_age_hours * 3600, frozenset(naics)

    def _ensure_file(self) -> Path:
        path = self.cache_path
        if path.exists() and time.time() - path.stat().st_mtime < self.max_age_s:
            return path
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".part")
        with self.client.stream("GET", self.url, timeout=600) as resp, tmp.open("wb") as fh:
            resp.raise_for_status()
            for chunk in resp.iter_bytes():
                fh.write(chunk)
        tmp.replace(path)
        return path

    def iter_opportunities(self, limit: int | None = None) -> Iterator[Opportunity]:
        yielded = 0
        # The extract is not strictly UTF-8; decode leniently so one bad byte can't stop the run.
        with self._ensure_file().open(encoding="utf-8", errors="replace", newline="") as fh:
            for row in csv.DictReader(fh):
                if _get(row, "NaicsCode") not in self.naics or _get(row, "BaseType") not in BASE_TYPES:
                    continue
                yield map_sam_csv_row(row)
                yielded += 1
                if limit is not None and yielded >= limit:
                    return
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit/test_sam_gov_bulk.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Live check (no key; about 210 MB download, cached for 20 h)**

Add `data/cache/` to `.gitignore`, then:

```bash
uv run python -c "
from pathlib import Path; from ingest.http import build_client
from ingest.sources.sam_gov_bulk import SamBulkAdapter
with build_client() as c:
    opps=list(SamBulkAdapter(c, cache_path=Path('data/cache/sam_full.csv')).iter_opportunities())
print(len(opps), sum(o.kind=='sbir' for o in opps), opps[0].title[:60])"
```
Expected: hundreds of R&D notices, some marked `sbir`.

- [ ] **Step 7: Commit**

```bash
git add ingest/sources/sam_gov_bulk.py tests/fixtures/sam_gov/bulk_sample.csv tests/unit/test_sam_gov_bulk.py .gitignore
git commit -m "feat(m0): SAM.gov daily bulk extract adapter (no quota, full descriptions)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```


---

### Task 8: Ingestion pipeline, company seed and CLI

**Files:**
- Create: `ingest/pipeline.py`, `ingest/company.py`, `ingest/__main__.py`, `data/company/profile.json`
- Test: `tests/db/test_pipeline.py`, `tests/db/test_company.py`

**Interfaces:**
- Consumes: `SourceAdapter`, `BlobStore`, `safe_key`, `is_allowed_attachment`, `download`, DB row classes, `db_session` fixture.
- Produces:
  - `ingest.pipeline.IngestStats` (dataclass: `seen`, `new`, `updated`, `unchanged`, `failed`, `attachments_stored`, `attachments_skipped`, `attachments_duplicate`, `errors: list[str]`)
  - `ingest.pipeline.run_ingest(adapter, session: Session, store: BlobStore, fetch: Callable[[str], bytes | None], *, limit: int | None = None, download_attachments: bool = True) -> IngestStats`
  - `ingest.company.seed_company(session: Session, profile_path: Path) -> uuid.UUID`
  - CLI: `python -m ingest run --source {grants_gov|sam_gov|sam_gov_api} [--limit N] [--no-attachments]`, `python -m ingest seed-company`, `python -m ingest stats`

- [ ] **Step 1: Write the company profile** (the facts the M1 eligibility rules check)

```json
{
  "name": "Lumen Grid Labs",
  "synthetic": true,
  "legal_form": "LLC",
  "entity_type": "for_profit",
  "employees": 32,
  "us_ownership_pct": 100,
  "foreign_affiliation": false,
  "state": "CO",
  "city": "Golden",
  "sam_registered": true,
  "uei": "LGLSYNTH0001",
  "cage": "9SYN1",
  "naics": ["541715", "335999", "541330"],
  "sbir_awards": {"I": 2, "II": 0},
  "founded": 2019,
  "core_capabilities": [
    "Solid-state battery management systems for grid storage",
    "Wide-bandgap (SiC/GaN) power converters for inverters",
    "Grid-forming inverter controls",
    "Hardware-in-the-loop testing of power electronics",
    "Battery degradation modeling"
  ],
  "preferences": {"exclude_agencies": [], "min_award_usd": 50000}
}
```

- [ ] **Step 2: Write the failing tests**

```python
# tests/db/test_company.py
import json
from pathlib import Path

import pytest
from sqlalchemy import select

from db.models import CompanyRow
from ingest.company import seed_company

pytestmark = pytest.mark.db


def test_seed_is_idempotent(db_session, tmp_path: Path):
    p = tmp_path / "profile.json"
    p.write_text(json.dumps({"name": "Lumen Grid Labs", "employees": 32}), encoding="utf-8")
    first = seed_company(db_session, p)
    p.write_text(json.dumps({"name": "Lumen Grid Labs", "employees": 33}), encoding="utf-8")
    second = seed_company(db_session, p)
    rows = db_session.scalars(select(CompanyRow)).all()
    assert first == second and len(rows) == 1 and rows[0].profile["employees"] == 33


def test_real_profile_has_rule_facts():
    profile = json.loads(Path("data/company/profile.json").read_text(encoding="utf-8"))
    for key in ("entity_type", "employees", "us_ownership_pct", "state", "sam_registered", "uei", "sbir_awards"):
        assert key in profile
    assert profile["synthetic"] is True
```

```python
# tests/db/test_pipeline.py
from collections.abc import Iterator
from pathlib import Path

import pytest
from sqlalchemy import func, select

from db.models import DocumentRow, IngestRunRow, OpportunityRow
from ingest.models import AttachmentRef, Opportunity, OppStatus
from ingest.pipeline import run_ingest
from ingest.storage import LocalBlobStore

pytestmark = pytest.mark.db


def opp(source_id: str, title: str = "Grid storage", attachments=None) -> Opportunity:
    return Opportunity(source="grants_gov", source_id=source_id, kind="grant", title=title,
                       status=OppStatus.open, description="d", agency="DOE",
                       source_url=f"https://x/{source_id}", attachments=attachments or [])


class FakeAdapter:
    name = "grants_gov"

    def __init__(self, opps: list[Opportunity]) -> None:
        self.opps = opps

    def iter_opportunities(self, limit=None) -> Iterator[Opportunity]:
        yield from self.opps[:limit]


class FakeFetch:
    def __init__(self, files: dict[str, bytes | None]) -> None:
        self.files, self.calls = files, []

    def __call__(self, url: str) -> bytes | None:
        self.calls.append(url)
        if url == "https://f/boom.pdf":
            raise RuntimeError("network down")
        return self.files.get(url)


PDF = AttachmentRef(url="https://f/a.pdf", file_name="a.pdf", mime_type="application/pdf")
ZIP = AttachmentRef(url="https://f/all.zip", file_name="all.zip", mime_type="application/zip")
BIG = AttachmentRef(url="https://f/big.pdf", file_name="big.pdf", mime_type="application/pdf")


def test_first_run_inserts_and_stores(db_session, tmp_path: Path):
    fetch = FakeFetch({"https://f/a.pdf": b"%PDF-a", "https://f/big.pdf": None})
    stats = run_ingest(FakeAdapter([opp("1", attachments=[PDF, ZIP, BIG])]), db_session,
                       LocalBlobStore(tmp_path), fetch)
    assert (stats.new, stats.attachments_stored, stats.attachments_skipped) == (1, 1, 2)
    assert fetch.calls == ["https://f/a.pdf", "https://f/big.pdf"]  # zip never fetched
    doc = db_session.scalars(select(DocumentRow)).one()
    assert doc.parse_status == "pending" and doc.corpus == "solicitation"
    assert (tmp_path / "raw/grants_gov/1/a.pdf").read_bytes() == b"%PDF-a"
    assert db_session.scalar(select(func.count()).select_from(IngestRunRow)) == 1


def test_rerun_is_idempotent_and_updates_in_place(db_session, tmp_path: Path):
    fetch = FakeFetch({"https://f/a.pdf": b"%PDF-a"})
    store = LocalBlobStore(tmp_path)
    run_ingest(FakeAdapter([opp("1", attachments=[PDF])]), db_session, store, fetch)
    again = run_ingest(FakeAdapter([opp("1", attachments=[PDF])]), db_session, store, fetch)
    assert (again.unchanged, again.new, again.updated) == (1, 0, 0)
    assert fetch.calls == ["https://f/a.pdf"]  # not re-downloaded
    changed = run_ingest(FakeAdapter([opp("1", title="Grid storage v2", attachments=[PDF])]),
                         db_session, store, fetch)
    assert changed.updated == 1 and changed.attachments_duplicate == 1
    assert db_session.scalar(select(func.count()).select_from(OpportunityRow)) == 1
    assert db_session.scalar(select(OpportunityRow.title)) == "Grid storage v2"
    assert db_session.scalar(select(func.count()).select_from(DocumentRow)) == 1


def test_one_bad_record_does_not_stop_the_run(db_session, tmp_path: Path):
    boom = AttachmentRef(url="https://f/boom.pdf", file_name="boom.pdf", mime_type="application/pdf")
    stats = run_ingest(FakeAdapter([opp("1", attachments=[boom]), opp("2")]), db_session,
                       LocalBlobStore(tmp_path), FakeFetch({}))
    assert stats.new == 2 and stats.failed == 0 and len(stats.errors) == 1
    assert "boom.pdf" in stats.errors[0]
```

- [ ] **Step 3: Run to see them fail**

Run: `uv run pytest tests/db/test_pipeline.py tests/db/test_company.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ingest.pipeline'`.

- [ ] **Step 4: Implement `ingest/pipeline.py`**

```python
"""Upsert opportunities, store their attachments, and record run statistics."""

import hashlib
import logging
import uuid
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import DocumentRow, IngestRunRow, OpportunityRow
from ingest.models import Opportunity
from ingest.sources.base import SourceAdapter
from ingest.storage import BlobStore, is_allowed_attachment, safe_key

log = logging.getLogger(__name__)


@dataclass
class IngestStats:
    seen: int = 0
    new: int = 0
    updated: int = 0
    unchanged: int = 0
    failed: int = 0
    attachments_stored: int = 0
    attachments_skipped: int = 0
    attachments_duplicate: int = 0
    errors: list[str] = field(default_factory=list)


def _apply(row: OpportunityRow, o: Opportunity, content_hash: str) -> None:
    row.kind, row.title, row.agency = o.kind, o.title, o.agency
    row.summary, row.url, row.status = o.description, o.source_url, o.status.value
    row.posted_at, row.close_at = o.key_dates.post_date, o.key_dates.close_date
    row.award_floor = o.funding.min_award_amount.amount if o.funding.min_award_amount else None
    row.award_ceiling = o.funding.max_award_amount.amount if o.funding.max_award_amount else None
    row.naics, row.assistance_listings = list(o.naics), list(o.assistance_listings)
    row.eligibility_codes = list(o.accepted_applicant_types)
    now = datetime.now(UTC)
    cg = o.to_commongrants(record_id=row.id, created_at=row.ingested_at or now, last_modified_at=now)
    row.raw = cg.model_dump(mode="json", by_alias=True, exclude_none=True)
    row.content_hash = content_hash


def _store_attachments(session: Session, row: OpportunityRow, o: Opportunity, store: BlobStore,
                       fetch: Callable[[str], bytes | None], stats: IngestStats) -> None:
    for att in o.attachments:
        if not is_allowed_attachment(att.mime_type, att.file_name):
            stats.attachments_skipped += 1
            continue
        try:
            data = fetch(att.url)
        except Exception as exc:  # one bad file must not stop the run
            stats.errors.append(f"{o.source}:{o.source_id}:{att.file_name}: {exc}")
            continue
        if data is None:
            stats.attachments_skipped += 1
            continue
        sha = hashlib.sha256(data).hexdigest()
        exists = session.scalar(select(DocumentRow.id).where(
            DocumentRow.opportunity_id == row.id, DocumentRow.sha256 == sha))
        if exists:
            stats.attachments_duplicate += 1
            continue
        uri = store.put(safe_key(o.source, o.source_id, att.file_name), data)
        session.add(DocumentRow(opportunity_id=row.id, corpus="solicitation", gcs_uri=uri,
                                mime=att.mime_type, title=att.file_name, sha256=sha,
                                parse_status="pending"))
        stats.attachments_stored += 1


def run_ingest(adapter: SourceAdapter, session: Session, store: BlobStore,
               fetch: Callable[[str], bytes | None], *, limit: int | None = None,
               download_attachments: bool = True) -> IngestStats:
    stats = IngestStats()
    started = datetime.now(UTC)
    for o in adapter.iter_opportunities(limit=limit):
        stats.seen += 1
        try:
            content_hash = o.content_hash()
            row = session.scalar(select(OpportunityRow).where(
                OpportunityRow.source == o.source, OpportunityRow.source_id == o.source_id))
            if row is not None and row.content_hash == content_hash:
                stats.unchanged += 1
                continue
            if row is None:
                row = OpportunityRow(id=uuid.uuid4(), source=o.source, source_id=o.source_id)
                session.add(row)
                stats.new += 1
            else:
                stats.updated += 1
            _apply(row, o, content_hash)
            session.flush()
            if download_attachments:
                _store_attachments(session, row, o, store, fetch, stats)
            session.commit()
        except Exception as exc:
            session.rollback()
            stats.failed += 1
            stats.errors.append(f"{o.source}:{o.source_id}: {exc}")
            log.exception("failed to ingest %s:%s", o.source, o.source_id)
    session.add(IngestRunRow(started_at=started, ended_at=datetime.now(UTC),
                             stats={"source": adapter.name, **asdict(stats)}))
    session.commit()
    return stats
```

- [ ] **Step 5: Implement `ingest/company.py`**

```python
import json
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from db.models import CompanyRow


def seed_company(session: Session, profile_path: Path) -> uuid.UUID:
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    row = session.scalar(select(CompanyRow).where(CompanyRow.name == profile["name"]))
    if row is None:
        row = CompanyRow(name=profile["name"], profile=profile)
        session.add(row)
    else:
        row.profile = profile
    session.commit()
    return row.id
```

- [ ] **Step 6: Implement the CLI `ingest/__main__.py`**

```python
"""python -m ingest {run,seed-company,stats}"""

import json
import logging
from pathlib import Path

import typer
from sqlalchemy import func, select

from app.config import get_settings
from db.models import DocumentRow, IngestRunRow, OpportunityRow
from db.session import make_engine, make_session_factory
from ingest.company import seed_company
from ingest.http import build_client, download
from ingest.pipeline import run_ingest
from ingest.sources.grants_gov import GrantsGovAdapter
from ingest.sources.sam_gov import SamGovAdapter
from ingest.sources.sam_gov_bulk import SamBulkAdapter
from ingest.storage import blob_store_from_root

cli = typer.Typer(no_args_is_help=True)


def _session():
    return make_session_factory(make_engine(get_settings().database_url))()


@cli.command()
def run(source: str = typer.Option(..., help="grants_gov, sam_gov (daily bulk extract) or sam_gov_api"),
        limit: int | None = typer.Option(None), attachments: bool = typer.Option(True)) -> None:
    logging.basicConfig(level=logging.INFO)
    s = get_settings()
    with build_client() as client, _session() as session:
        if source == "grants_gov":
            if s.simpler_grants_api_key is None:
                raise typer.BadParameter("SIMPLER_GRANTS_API_KEY is not set")
            adapter = GrantsGovAdapter(client, s.simpler_grants_api_key.get_secret_value())
        elif source == "sam_gov":
            adapter = SamBulkAdapter(client, cache_path=Path("data/cache/sam_full.csv"))
        elif source == "sam_gov_api":
            if s.sam_api_key is None:
                raise typer.BadParameter("SAM_API_KEY is not set")
            adapter = SamGovAdapter(client, s.sam_api_key.get_secret_value(),
                                    request_budget=s.sam_daily_request_budget)
        else:
            raise typer.BadParameter(f"unknown source {source!r}")

        def fetch(url: str) -> bytes | None:
            return download(client, url, max_bytes=s.max_attachment_bytes)

        if source == "sam_gov_api" and attachments:
            # SAM attachment downloads may count against the ~10 requests/day key quota.
            # Links are kept in raw/customFields; M1's Analyze agent fetches them on demand.
            typer.echo("sam_gov: attachment download deferred to on-demand (quota)", err=True)
            attachments = False
        stats = run_ingest(adapter, session, blob_store_from_root(s.blob_root), fetch,
                           limit=limit, download_attachments=attachments)
    typer.echo(json.dumps({k: v for k, v in stats.__dict__.items() if k != "errors"}, indent=2))
    for e in stats.errors[:20]:
        typer.echo(f"error: {e}", err=True)


@cli.command("seed-company")
def seed(profile: Path = Path("data/company/profile.json")) -> None:
    with _session() as session:
        typer.echo(f"company id: {seed_company(session, profile)}")


@cli.command()
def stats() -> None:
    with _session() as session:
        by_source = session.execute(
            select(OpportunityRow.source, OpportunityRow.status, func.count())
            .group_by(OpportunityRow.source, OpportunityRow.status)).all()
        docs = session.scalar(select(func.count()).select_from(DocumentRow))
        opps_with_docs = session.scalar(select(func.count(func.distinct(DocumentRow.opportunity_id))))
        last = session.scalar(select(IngestRunRow).order_by(IngestRunRow.started_at.desc()).limit(1))
    for src, status, n in by_source:
        typer.echo(f"{src:12} {status:11} {n}")
    typer.echo(f"documents: {docs}  opportunities with documents: {opps_with_docs}")
    if last:
        typer.echo(f"last run: {last.started_at:%Y-%m-%d %H:%M} {last.stats.get('source')}")


if __name__ == "__main__":
    cli()
```

- [ ] **Step 7: Run tests**

Run: `uv run pytest tests/db -v`
Expected: all PASS (3 migration + 3 pipeline + 2 company).

- [ ] **Step 8: Commit**

```bash
git add ingest/pipeline.py ingest/company.py ingest/__main__.py data/company/profile.json tests/db
git commit -m "feat(m0): ingestion pipeline with idempotent upserts, attachment storage and CLI

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8b: Raw zone, provenance and replay

**Files:**
- Create: `ingest/raw.py`
- Modify: `ingest/storage.py` (add `get`, `list`), `ingest/sources/grants_gov.py`, `ingest/sources/sam_gov.py`, `ingest/sources/sam_gov_bulk.py`, `ingest/__main__.py`
- Test: `tests/unit/test_raw_zone.py`

**Interfaces:**
- Consumes: `BlobStore`, the three adapters, `run_ingest`.
- Produces:
  - `BlobStore.get(key: str) -> bytes`, `BlobStore.list(prefix: str) -> list[str]` (store-relative keys, sorted), on both `LocalBlobStore` and `GCSBlobStore`
  - `ingest.raw.RawArchive(store: BlobStore, source: str, run_date: date)` with `.prefix`, `.key(name) -> str`, `.put_json(name, payload) -> str` (returns the key), `.put_bytes(name, data) -> str`, `.iter_json(name_prefix="") -> Iterator[tuple[str, Any]]`
  - Adapter attribute `version: str` (`"grants_gov/1"`, `"sam_gov/1"`, `"sam_gov_api/1"`) and constructor argument `archive: RawArchive | None = None`
  - `ingest.raw.replay_grants_gov(archive) -> Iterator[Opportunity]`, `ingest.raw.replay_sam_bulk(archive) -> Iterator[Opportunity]`, `ingest.raw.ReplayAdapter(name, version, factory)`
  - CLI: `python -m ingest replay --source {grants_gov|sam_gov} --date YYYY-MM-DD`

**Why (the data-team pattern):** every response we download is saved unchanged before we transform it. This is the "bronze" layer of the medallion pattern; the `opportunities` table is "silver". If a mapping bug is found later, fix the mapper and **replay** the saved files: no API calls, no quota, and the result is reproducible. Every record also stores where it came from (`raw_uri`), when it was fetched (`fetched_at`), and which adapter version produced it (`adapter_version`).

Layout: `raw/api/<source>/<YYYY-MM-DD>/<name>`, with keys sanitized. Attachments keep their existing `raw/<source>/<source_id>/<file>` layout.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_raw_zone.py
import json
from datetime import date
from pathlib import Path

import httpx
import respx

from ingest.http import build_client
from ingest.raw import RawArchive, replay_grants_gov, replay_sam_bulk
from ingest.sources.grants_gov import GRANTS_BASE, GrantsGovAdapter
from ingest.sources.sam_gov_bulk import SAM_BULK_URL, SamBulkAdapter
from ingest.storage import LocalBlobStore

FIX = Path("tests/fixtures/grants_gov")
DAY = date(2026, 10, 7)


def load(name: str) -> dict:
    return json.loads((FIX / name).read_text(encoding="utf-8"))


def test_archive_round_trip_and_listing(tmp_path: Path):
    archive = RawArchive(LocalBlobStore(tmp_path), "grants_gov", DAY)
    key = archive.put_json("detail-../../evil", {"a": 1})
    assert key == "raw/api/grants_gov/2026-10-07/detail-_evil.json"
    archive.put_json("search-page-0001", {"b": 2})
    assert [k for k, _ in archive.iter_json("detail-")] == [key]
    assert len(list(archive.iter_json())) == 2


@respx.mock
def test_grants_adapter_archives_raw_and_sets_provenance(tmp_path: Path):
    respx.post(f"{GRANTS_BASE}/v1/opportunities/search").mock(
        return_value=httpx.Response(200, json=load("search_page1.json")))
    respx.get(f"{GRANTS_BASE}/v1/opportunities/11111111-1111-1111-1111-111111111111").mock(
        return_value=httpx.Response(200, json=load("detail_full.json")))
    respx.get(f"{GRANTS_BASE}/v1/opportunities/22222222-2222-2222-2222-222222222222").mock(
        return_value=httpx.Response(200, json=load("detail_sparse.json")))
    archive = RawArchive(LocalBlobStore(tmp_path), "grants_gov", DAY)
    with build_client() as c:
        live = list(GrantsGovAdapter(c, "k", page_size=2, min_interval_s=0, archive=archive).iter_opportunities())
    assert live[0].raw_uri == "raw/api/grants_gov/2026-10-07/detail-11111111-1111-1111-1111-111111111111.json"
    assert (tmp_path / "raw/api/grants_gov/2026-10-07/search-page-0001.json").exists()
    replayed = list(replay_grants_gov(archive))
    assert sorted(o.content_hash() for o in replayed) == sorted(o.content_hash() for o in live)


@respx.mock
def test_sam_bulk_archives_csv_and_replays(tmp_path: Path):
    respx.get(SAM_BULK_URL).mock(return_value=httpx.Response(
        200, content=Path("tests/fixtures/sam_gov/bulk_sample.csv").read_bytes()))
    store = LocalBlobStore(tmp_path / "blobs")
    archive = RawArchive(store, "sam_gov", DAY)
    with build_client() as c:
        live = list(SamBulkAdapter(c, cache_path=tmp_path / "sam.csv", archive=archive).iter_opportunities())
    assert live[0].raw_uri == "raw/api/sam_gov/2026-10-07/ContractOpportunitiesFullCSV.csv#n-101"
    assert [o.source_id for o in replay_sam_bulk(archive)] == [o.source_id for o in live]
```

Also add to `tests/unit/test_ingest_models.py`:

```python
def test_raw_uri_is_provenance_not_content():
    assert _opp().content_hash() == _opp(raw_uri="raw/api/x/2026-10-07/a.json").content_hash()
```

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/unit/test_raw_zone.py tests/unit/test_ingest_models.py -v`
Expected: FAIL (`ingest.raw` missing; `Opportunity` has no `raw_uri`).

- [ ] **Step 3: `Opportunity.raw_uri` (provenance, excluded from the content hash)**

In `ingest/models.py`, add to `Opportunity`:

```python
    raw_uri: str | None = Field(default=None, exclude=True)  # provenance; not part of content
```
`exclude=True` keeps it out of `model_dump()`, so `content_hash()` ignores it.

- [ ] **Step 4: `get` and `list` on both blob stores** (`ingest/storage.py`)

```python
class BlobStore(Protocol):
    def put(self, key: str, data: bytes) -> str: ...
    def exists(self, key: str) -> bool: ...
    def get(self, key: str) -> bytes: ...
    def list(self, prefix: str) -> list[str]: ...
```
`LocalBlobStore`:

```python
    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def list(self, prefix: str) -> list[str]:
        base = self._path(prefix.rsplit("/", 1)[0]) if "/" in prefix else self.root
        if not base.exists():
            return []
        keys = (f.relative_to(self.root).as_posix() for f in base.rglob("*") if f.is_file())
        return sorted(k for k in keys if k.startswith(prefix))
```
`GCSBlobStore`:

```python
    def get(self, key: str) -> bytes:
        return self._bucket.blob(key).download_as_bytes()

    def list(self, prefix: str) -> list[str]:
        return sorted(b.name for b in self._client.list_blobs(self.bucket_name, prefix=prefix))
```

- [ ] **Step 5: `ingest/raw.py`**

```python
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
        segments = [s for s in name.replace("\\", "/").split("/") if s not in ("", ".", "..")]
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


def replay_sam_bulk(archive: RawArchive, naics: frozenset[str] | None = None) -> Iterator[Opportunity]:
    from ingest.sources.sam_gov import R_AND_D_NAICS
    from ingest.sources.sam_gov_bulk import BASE_TYPES, map_sam_csv_row

    allowed = naics or frozenset(R_AND_D_NAICS)
    key = archive.key(SAM_CSV_NAME)
    text = archive.store.get(key).decode("utf-8", errors="replace")
    for row in csv.DictReader(io.StringIO(text, newline="")):
        if (row.get("NaicsCode") or "").strip() in allowed and (row.get("BaseType") or "").strip() in BASE_TYPES:
            o = map_sam_csv_row(row)
            yield o.model_copy(update={"raw_uri": f"{key}#{o.source_id}"})


class ReplayAdapter:
    def __init__(self, name: str, version: str, factory: Callable[[], Iterator[Opportunity]]) -> None:
        self.name, self.version, self._factory = name, f"{version}+replay", factory

    def iter_opportunities(self, limit: int | None = None) -> Iterator[Opportunity]:
        for i, o in enumerate(self._factory()):
            if limit is not None and i >= limit:
                return
            yield o
```

- [ ] **Step 6: Adapters archive what they download and record provenance**

`ingest/sources/grants_gov.py`: add `version = "grants_gov/1"` under `name`, add the constructor argument `archive: "RawArchive | None" = None` (store it as `self.archive`), and in `iter_opportunities`:

```python
            payload = self._call("POST", f"{GRANTS_BASE}/v1/opportunities/search", json=body)
            if self.archive:
                self.archive.put_json(f"search-page-{page:04d}", payload)
            for item in payload.get("data") or []:
                detail = self._call("GET", f"{GRANTS_BASE}/v1/opportunities/{item['opportunity_id']}")
                raw_key = self.archive.put_json(f"detail-{item['opportunity_id']}", detail) if self.archive else None
                yield map_grants_gov(detail["data"]).model_copy(update={"raw_uri": raw_key})
```
Import `RawArchive` under `if TYPE_CHECKING:` to avoid a runtime import cycle.

`ingest/sources/sam_gov_bulk.py`: add `version = "sam_gov/1"`, the `archive` argument, and archive the CSV only when it was freshly downloaded. Change `_ensure_file` to return `(path, downloaded: bool)`. In `iter_opportunities`:

```python
        path, downloaded = self._ensure_file()
        csv_key = None
        if self.archive:
            csv_key = self.archive.key(SAM_CSV_NAME)
            if downloaded or not self.archive.store.exists(csv_key):
                self.archive.put_bytes(SAM_CSV_NAME, path.read_bytes())
        ...
                o = map_sam_csv_row(row)
                yield o.model_copy(update={"raw_uri": f"{csv_key}#{o.source_id}"}) if csv_key else o
```
(Import `SAM_CSV_NAME` from `ingest.raw`.) Update Task 7b's `test_fresh_cache_skips_download_and_stale_cache_refreshes` only if the changed return type affects it; it doesn't, because it calls `iter_opportunities`.

`ingest/sources/sam_gov.py` (API): add `version = "sam_gov_api/1"` and the `archive` argument, and archive each search response with `self.archive.put_json(f"search-{ptype}-{naics}-{offset}", payload)`.

- [ ] **Step 7: CLI wiring**

In `ingest/__main__.py` `run`: build `archive = RawArchive(store, adapter.name, date.today())` (create the store once as `store = blob_store_from_root(s.blob_root)`, then pass `archive=archive` to whichever adapter is constructed). Add:

```python
@cli.command()
def replay(source: str = typer.Option(..., help="grants_gov or sam_gov"),
           day: str = typer.Option(..., "--date", help="YYYY-MM-DD of the archived run")) -> None:
    """Rebuild opportunities from the raw zone without calling any API."""
    s = get_settings()
    store = blob_store_from_root(s.blob_root)
    archive = RawArchive(store, source, date.fromisoformat(day))
    factories = {"grants_gov": ("grants_gov/1", lambda: replay_grants_gov(archive)),
                 "sam_gov": ("sam_gov/1", lambda: replay_sam_bulk(archive))}
    if source not in factories:
        raise typer.BadParameter(f"unknown source {source!r}")
    version, factory = factories[source]
    with _session() as session:
        stats = run_ingest(ReplayAdapter(source, version, factory), session, store,
                           fetch=lambda url: None, download_attachments=False)
    typer.echo(json.dumps({k: v for k, v in stats.__dict__.items() if k != "errors"}, indent=2))
```

- [ ] **Step 8: Provenance columns are written by the pipeline**

In `ingest/pipeline.py`, change `_apply(row, o, content_hash)` to `_apply(row, o, content_hash, adapter_version)` and add at its end:

```python
    row.fetched_at = now
    row.raw_uri = o.raw_uri
    row.adapter_version = adapter_version
```
Call it as `_apply(row, o, content_hash, getattr(adapter, "version", "unknown"))`. In `tests/db/test_pipeline.py`, give `FakeAdapter` a `version = "fake/1"` and append to `test_first_run_inserts_and_stores`:

```python
    row = db_session.scalars(select(OpportunityRow)).one()
    assert row.adapter_version == "fake/1" and row.fetched_at is not None
```

- [ ] **Step 9: Run tests**

Run: `uv run pytest tests/unit tests/db -v`
Expected: all PASS (3 new raw-zone tests, the provenance model test and the extended pipeline test included).

- [ ] **Step 10: Commit**

```bash
git add ingest tests
git commit -m "feat(m0): raw zone archiving, provenance columns and replay command

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8c: Automatic data-quality checks

**Files:**
- Create: `ingest/quality.py`
- Modify: `ingest/pipeline.py`, `ingest/__main__.py`
- Test: `tests/db/test_quality.py`

**Interfaces:**
- Consumes: `OpportunityRow`, `IngestRunRow`, `run_ingest`.
- Produces:
  - `ingest.quality.QualityIssue` (frozen dataclass: `check: str`, `severity: Literal["error", "warning"]`, `message: str`)
  - `ingest.quality.THRESHOLDS` (dict)
  - `ingest.quality.previous_full_run_seen(session, source: str) -> int | None`
  - `ingest.quality.check_run(session, source: str, *, seen: int, failed: int, previous_seen: int | None) -> list[QualityIssue]`
  - `IngestStats.quality_issues: list[dict]`; the CLI exits with code 1 when any issue has severity `error`, so a scheduled Cloud Run Job shows as **failed**

**Checks** (run after every full run, i.e. with no `--limit`):

| ID | Check | Severity |
|---|---|---|
| Q1 | The run saw zero records | error |
| Q2 | Records seen fell below 70% of the previous full run (the source changed or broke) | error |
| Q3 | More than 5% of records failed to ingest | error |
| Q4 | More than 10% of open opportunities have no close date (a mapping regression) | warning |

- [ ] **Step 1: Write the failing tests**

```python
# tests/db/test_quality.py
import uuid
from datetime import date

import pytest

from db.models import IngestRunRow, OpportunityRow
from ingest.quality import check_run, previous_full_run_seen

pytestmark = pytest.mark.db


def _ids(issues):
    return {i.check for i in issues}


def _opp(source_id: str, close: date | None) -> OpportunityRow:
    return OpportunityRow(id=uuid.uuid4(), source="grants_gov", source_id=source_id, kind="grant",
                          title="t", agency="a", summary="", url="u", status="open", close_at=close,
                          naics=[], assistance_listings=[], eligibility_codes=[], raw={}, content_hash="h")


def test_empty_run_is_an_error(db_session):
    assert "Q1_empty" in _ids(check_run(db_session, "grants_gov", seen=0, failed=0, previous_seen=None))


def test_volume_drop_against_previous_full_run(db_session):
    db_session.add(IngestRunRow(stats={"source": "grants_gov", "limit": None, "seen": 100}))
    db_session.add(IngestRunRow(stats={"source": "grants_gov", "limit": 10, "seen": 10}))  # ignored: partial
    db_session.commit()
    prev = previous_full_run_seen(db_session, "grants_gov")
    assert prev == 100
    assert "Q2_volume_drop" in _ids(check_run(db_session, "grants_gov", seen=50, failed=0, previous_seen=prev))
    assert "Q2_volume_drop" not in _ids(check_run(db_session, "grants_gov", seen=80, failed=0, previous_seen=prev))


def test_error_rate(db_session):
    assert "Q3_error_rate" in _ids(check_run(db_session, "grants_gov", seen=100, failed=10, previous_seen=None))
    assert "Q3_error_rate" not in _ids(check_run(db_session, "grants_gov", seen=100, failed=5, previous_seen=None))


def test_missing_close_dates_warning(db_session):
    db_session.add_all([_opp(str(i), date(2026, 12, 1)) for i in range(8)] + [_opp("x", None), _opp("y", None)])
    db_session.commit()
    issues = check_run(db_session, "grants_gov", seen=10, failed=0, previous_seen=None)
    q4 = [i for i in issues if i.check == "Q4_missing_close_dates"]
    assert q4 and q4[0].severity == "warning"
```

And extend `tests/db/test_pipeline.py`:

```python
def test_full_run_records_quality_issues(db_session, tmp_path: Path):
    stats = run_ingest(FakeAdapter([]), db_session, LocalBlobStore(tmp_path), FakeFetch({}))
    assert any(i["check"] == "Q1_empty" and i["severity"] == "error" for i in stats.quality_issues)
    run = db_session.scalars(select(IngestRunRow)).one()
    assert run.stats["quality_issues"][0]["check"] == "Q1_empty" and run.stats["limit"] is None
```

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/db/test_quality.py tests/db/test_pipeline.py -v`
Expected: FAIL (`ingest.quality` missing).

- [ ] **Step 3: Implement `ingest/quality.py`**

```python
"""Post-run data-quality checks. Errors fail the run; warnings are recorded."""

from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from db.models import IngestRunRow, OpportunityRow

THRESHOLDS = {"min_seen_ratio": 0.70, "max_failed_ratio": 0.05, "max_open_missing_close": 0.10}


@dataclass(frozen=True)
class QualityIssue:
    check: str
    severity: Literal["error", "warning"]
    message: str


def previous_full_run_seen(session: Session, source: str) -> int | None:
    stats = session.scalar(
        select(IngestRunRow.stats)
        .where(IngestRunRow.stats["source"].astext == source)
        .where(IngestRunRow.stats["limit"].astext.is_(None))
        .order_by(IngestRunRow.started_at.desc(), IngestRunRow.id.desc())
        .limit(1))
    return int(stats["seen"]) if stats and "seen" in stats else None


def check_run(session: Session, source: str, *, seen: int, failed: int,
              previous_seen: int | None) -> list[QualityIssue]:
    issues: list[QualityIssue] = []
    if seen == 0:
        issues.append(QualityIssue("Q1_empty", "error", f"{source}: no records seen"))
    if previous_seen and seen < THRESHOLDS["min_seen_ratio"] * previous_seen:
        issues.append(QualityIssue("Q2_volume_drop", "error",
                                   f"{source}: {seen} records vs {previous_seen} last full run"))
    if seen and failed / seen > THRESHOLDS["max_failed_ratio"]:
        issues.append(QualityIssue("Q3_error_rate", "error", f"{source}: {failed}/{seen} records failed"))
    open_q = select(func.count()).select_from(OpportunityRow).where(
        OpportunityRow.source == source, OpportunityRow.status == "open")
    open_total = session.scalar(open_q) or 0
    missing = session.scalar(open_q.where(OpportunityRow.close_at.is_(None))) or 0
    if open_total and missing / open_total > THRESHOLDS["max_open_missing_close"]:
        issues.append(QualityIssue("Q4_missing_close_dates", "warning",
                                   f"{source}: {missing}/{open_total} open opportunities lack a close date"))
    return issues
```
`stats["limit"].astext.is_(None)` matches both a JSON `null` and a missing key, because `->>` returns SQL NULL for both. The second `IngestRunRow` in `test_volume_drop_against_previous_full_run` is inserted after the first in the same transaction, so `started_at` ties. The `id.desc()` tiebreak doesn't guarantee insertion order with random UUIDs, but the partial run is filtered out by the `limit` condition, so the test is deterministic.

- [ ] **Step 4: Wire into the pipeline and CLI**

`ingest/pipeline.py`: add `quality_issues: list[dict] = field(default_factory=list)` to `IngestStats`. In `run_ingest`, compute `prev = previous_full_run_seen(session, adapter.name)` before the loop, and after it:

```python
    if limit is None:
        stats.quality_issues = [asdict(i) for i in check_run(
            session, adapter.name, seen=stats.seen, failed=stats.failed, previous_seen=prev)]
    session.add(IngestRunRow(started_at=started, ended_at=datetime.now(UTC),
                             stats={"source": adapter.name, "limit": limit, **asdict(stats)}))
```
(This replaces the existing `IngestRunRow` line.)

`ingest/__main__.py` `run` (and `replay`): after printing the stats, add:

```python
    for issue in stats.quality_issues:
        typer.echo(f"quality {issue['severity']}: {issue['check']} - {issue['message']}", err=True)
    if any(i["severity"] == "error" for i in stats.quality_issues):
        raise typer.Exit(code=1)
```

- [ ] **Step 5: Run tests**

Run: `uv run pytest tests/unit tests/db -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add ingest tests
git commit -m "feat(m0): post-run data-quality checks that fail the run on errors

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: Synthetic company documents (Lumen Grid Labs)

**Files:**
- Create: `data/company/README.md`, `data/company/docs/capability-statement.md`, `data/company/docs/past-proposal-0{1..5}-*.md`, `data/company/docs/project-report-0{1..3}-*.md`, `data/company/docs/bio-0{1..4}-*.md`
- Test: `tests/unit/test_company_docs.py`

**Interfaces:**
- Produces: the company corpus that M1 parses and M3 retrieves from. It's the evidence the drafter may cite, so the facts must be consistent across files.

These documents are the **Draft** module's ground truth. Write them as a real small company would, in plain English with concrete numbers. Every file starts with the line `> Synthetic document for grant-capture-agent evaluation. All people, numbers and results are fictional.`

**Facts every document must agree with** (copy exactly):

| Fact | Value |
|---|---|
| Company | Lumen Grid Labs, LLC · Golden, Colorado · founded 2019 · 32 employees · 100% U.S.-owned · UEI LGLSYNTH0001 |
| Products | **LGL-BMS3** solid-state battery management system (cell balancing ±2 mV, SoC estimation error ≤ 1.5%) · **HelioLink 250** 250 kW SiC grid-forming inverter (98.7% peak efficiency) |
| Lab | 1,800 sq ft power-electronics lab, 500 kW regenerative grid simulator, OPAL-RT hardware-in-the-loop rig |
| Prior awards (fictional) | DOE SBIR Phase I 2023, "Degradation-aware BMS for second-life batteries" ($200,000; met all milestones) · NSF SBIR Phase I 2024, "Grid-forming control for weak grids" ($275,000; 14% faster fault ride-through than baseline) |
| Partner | Front Range Utility Cooperative (letter of support 2025) · Colorado School of Mines (STTR research partner) |
| People | Dr. Maya Okafor (CEO, PI on both awards) · Ravi Deshmukh (CTO, power electronics) · Elena Brandt (lead battery scientist) · Jordan Lee (test engineer) |

**Documents to write** (word counts ±20%):

| File | Words | Must contain |
|---|---|---|
| `capability-statement.md` | 600 | Core capabilities (from profile), both products with specs, lab equipment, NAICS 541715/335999/541330, differentiators, past performance summary |
| `past-proposal-01-doe-bms-technical.md` | 900 | Technical approach of the 2023 DOE proposal: problem, innovation, 3 objectives, work plan with 4 tasks, risk table |
| `past-proposal-02-doe-bms-commercialization.md` | 600 | Market (second-life batteries), customers, revenue model, path to Phase II |
| `past-proposal-03-nsf-gfm-project-description.md` | 900 | Intellectual merit, broader impacts, technical objectives, milestones for the 2024 NSF proposal |
| `past-proposal-04-nsf-gfm-key-personnel.md` | 400 | Roles and percent effort for the four people |
| `past-proposal-05-facilities-equipment.md` | 400 | Lab, equipment list, safety practices, access to the Mines partner lab |
| `project-report-01-doe-phase1-final.md` | 800 | Results vs. milestones, measured numbers (cell balancing, SoC error), lessons learned |
| `project-report-02-nsf-phase1-final.md` | 800 | Fault ride-through results (14% improvement), test conditions, next steps |
| `project-report-03-heliolink-field-pilot.md` | 600 | 2025 pilot with Front Range Utility Cooperative: 6-week deployment, 99.2% availability, one inverter trip and its root cause |
| `bio-01-maya-okafor.md` … `bio-04-jordan-lee.md` | 250 each | Education, experience, relevant publications or patents, and **a contact line using `@example.com` emails and `555-01xx` phone numbers** (M3 tests Sensitive Data Protection redaction against these) |

Also write `data/company/README.md` (about 100 words) explaining that the company is fictional, what each file is for, and that the facts table above is authoritative.

**Important gaps (do not fill these in):** there is **no** past work on hydrogen, cybersecurity or offshore wind. M3's evals check that the drafter flags these as gaps instead of inventing evidence.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_company_docs.py
import re
from pathlib import Path

DOCS = Path("data/company/docs")
DISCLAIMER = "> Synthetic document for grant-capture-agent evaluation."
EXPECTED = {
    "capability-statement.md": 600, "past-proposal-01-doe-bms-technical.md": 900,
    "past-proposal-02-doe-bms-commercialization.md": 600, "past-proposal-03-nsf-gfm-project-description.md": 900,
    "past-proposal-04-nsf-gfm-key-personnel.md": 400, "past-proposal-05-facilities-equipment.md": 400,
    "project-report-01-doe-phase1-final.md": 800, "project-report-02-nsf-phase1-final.md": 800,
    "project-report-03-heliolink-field-pilot.md": 600, "bio-01-maya-okafor.md": 250,
    "bio-02-ravi-deshmukh.md": 250, "bio-03-elena-brandt.md": 250, "bio-04-jordan-lee.md": 250,
}


def test_all_documents_present_with_disclaimer_and_length():
    for name, words in EXPECTED.items():
        text = (DOCS / name).read_text(encoding="utf-8")
        assert text.startswith(DISCLAIMER), name
        n = len(text.split())
        assert 0.8 * words <= n <= 1.2 * words, f"{name}: {n} words"


def test_contact_details_are_obviously_fake():
    for path in DOCS.glob("*.md"):
        text = path.read_text(encoding="utf-8")
        for email in re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", text):
            assert email.endswith("@example.com"), (path.name, email)
        for phone in re.findall(r"\b\d{3}-\d{3}-\d{4}\b", text):
            assert phone.split("-")[1] == "555", (path.name, phone)


def test_known_gaps_stay_gaps():
    corpus = " ".join(p.read_text(encoding="utf-8").lower() for p in DOCS.glob("*.md"))
    for topic in ("hydrogen", "cybersecurity", "offshore wind"):
        assert topic not in corpus, topic
```

- [ ] **Step 2: Run to see it fail**

Run: `uv run pytest tests/unit/test_company_docs.py -v`
Expected: FAIL (`FileNotFoundError`).

- [ ] **Step 3: Write the 13 documents and the README** following the tables above.

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_company_docs.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Seed the company row in the dev DB**

Run: `uv run python -m ingest seed-company`
Expected: `company id: <uuid>`.

- [ ] **Step 6: Commit**

```bash
git add data/company tests/unit/test_company_docs.py
git commit -m "feat(m0): synthetic Lumen Grid Labs company corpus

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 10: Eval harness skeleton and labeling guide

**Files:**
- Create: `evals/__init__.py` (empty), `evals/metrics.py`, `evals/report.py`, `evals/run.py`, `evals/LABELING.md`, `evals/data/golden/README.md`, `evals/data/dev/README.md`
- Test: `tests/unit/test_metrics.py`, `tests/unit/test_eval_report.py`

**Interfaces:**
- Produces:
  - `evals.metrics.precision_recall(predicted: set, actual: set) -> tuple[float, float]`
  - `evals.metrics.precision_at_k(ranked: list[str], relevant: set[str], k: int) -> float`
  - `evals.metrics.ndcg_at_k(ranked: list[str], gains: dict[str, int], k: int) -> float`
  - `evals.metrics.cohen_kappa(a: list, b: list) -> float`
  - `evals.report.MetricResult` (dataclass: `suite`, `metric`, `value: float | None`, `target: float | None`, `higher_is_better: bool = True`; property `passed: bool | None`)
  - `evals.report.write_report(results: list[MetricResult], out_dir: Path, run_id: str) -> tuple[Path, Path]`
  - `evals.run.SUITES: dict[str, Callable[[], list[MetricResult]]]`; CLI `python -m evals.run --suite smoke --out reports/local`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_metrics.py
import pytest

from evals.metrics import cohen_kappa, ndcg_at_k, precision_at_k, precision_recall


def test_precision_recall_including_empty_edges():
    assert precision_recall({"a", "b"}, {"b", "c"}) == (0.5, 0.5)
    assert precision_recall(set(), set()) == (1.0, 1.0)
    assert precision_recall(set(), {"a"}) == (0.0, 0.0)
    assert precision_recall({"a"}, set()) == (0.0, 1.0)


def test_precision_at_k_divides_by_k():
    assert precision_at_k(["a", "x", "b"], {"a", "b"}, k=3) == pytest.approx(2 / 3)
    assert precision_at_k(["a"], {"a"}, k=10) == pytest.approx(0.1)


def test_ndcg_hand_computed():
    # dcg = 0 + 3/log2(3) + 1/2 = 2.3928 ; idcg = 3 + 1/log2(3) = 3.6309
    assert ndcg_at_k(["a", "b", "c"], {"a": 0, "b": 2, "c": 1}, k=3) == pytest.approx(0.6590, abs=1e-3)
    assert ndcg_at_k(["a"], {"a": 0}, k=5) == 0.0


def test_cohen_kappa_hand_computed():
    assert cohen_kappa([1, 1, 0, 0], [1, 0, 0, 0]) == pytest.approx(0.5)
    assert cohen_kappa(["x", "x"], ["x", "x"]) == 1.0
    with pytest.raises(ValueError):
        cohen_kappa([1], [1, 0])
```

```python
# tests/unit/test_eval_report.py
import json
from pathlib import Path

from evals.report import MetricResult, write_report
from evals.run import main


def test_report_files_and_pass_logic(tmp_path: Path):
    results = [MetricResult("knockout", "recall", 0.96, 0.95),
               MetricResult("system", "p95_latency_s", 120.0, 90.0, higher_is_better=False),
               MetricResult("draft", "faithfulness", None, 0.90)]
    assert [r.passed for r in results] == [True, False, None]
    js, md = write_report(results, tmp_path, run_id="t1")
    data = json.loads(js.read_text(encoding="utf-8"))
    assert data["run_id"] == "t1" and len(data["results"]) == 3
    assert "| knockout | recall | 0.960 | 0.950 | pass |" in md.read_text(encoding="utf-8")


def test_smoke_run_with_no_suites_writes_empty_report(tmp_path: Path):
    assert main(["--suite", "smoke", "--out", str(tmp_path)]) == 0
    assert list(tmp_path.glob("*.json")) and list(tmp_path.glob("*.md"))
```

- [ ] **Step 2: Run to see them fail**

Run: `uv run pytest tests/unit/test_metrics.py tests/unit/test_eval_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'evals'`.

- [ ] **Step 3: Implement**

```python
# evals/metrics.py
"""Plain metric functions. No model calls, so they are deterministic and unit-tested."""

import math
from collections import Counter
from collections.abc import Hashable, Sequence


def precision_recall(predicted: set, actual: set) -> tuple[float, float]:
    tp = len(predicted & actual)
    precision = (1.0 if not actual else 0.0) if not predicted else tp / len(predicted)
    recall = 1.0 if not actual else tp / len(actual)
    return precision, recall


def precision_at_k(ranked: Sequence[str], relevant: set[str], k: int) -> float:
    return sum(1 for item in ranked[:k] if item in relevant) / k


def ndcg_at_k(ranked: Sequence[str], gains: dict[str, int], k: int) -> float:
    def dcg(values: Sequence[int]) -> float:
        return sum((2**g - 1) / math.log2(i + 2) for i, g in enumerate(values))

    actual = dcg([gains.get(item, 0) for item in ranked[:k]])
    ideal = dcg(sorted(gains.values(), reverse=True)[:k])
    return 0.0 if ideal == 0 else actual / ideal


def cohen_kappa(a: Sequence[Hashable], b: Sequence[Hashable]) -> float:
    if len(a) != len(b) or not a:
        raise ValueError("label lists must be non-empty and the same length")
    n = len(a)
    observed = sum(x == y for x, y in zip(a, b, strict=True)) / n
    ca, cb = Counter(a), Counter(b)
    expected = sum(ca[label] * cb[label] for label in ca.keys() | cb.keys()) / (n * n)
    return 1.0 if expected == 1 else (observed - expected) / (1 - expected)
```

```python
# evals/report.py
import json
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class MetricResult:
    suite: str
    metric: str
    value: float | None
    target: float | None
    higher_is_better: bool = True

    @property
    def passed(self) -> bool | None:
        if self.value is None or self.target is None:
            return None
        return self.value >= self.target if self.higher_is_better else self.value <= self.target


def _fmt(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.3f}"


def write_report(results: list[MetricResult], out_dir: Path, run_id: str) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    js = out_dir / f"eval-{run_id}.json"
    md = out_dir / f"eval-{run_id}.md"
    js.write_text(json.dumps({"run_id": run_id,
                              "results": [{**asdict(r), "passed": r.passed} for r in results]}, indent=2),
                  encoding="utf-8")
    lines = [f"# Eval report `{run_id}`", "", "| suite | metric | value | target | result |",
             "|---|---|---|---|---|"]
    status = {True: "pass", False: "FAIL", None: "pending"}
    lines += [f"| {r.suite} | {r.metric} | {_fmt(r.value)} | {_fmt(r.target)} | {status[r.passed]} |"
              for r in results]
    if not results:
        lines.append("| (no suites registered yet) | | | | |")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return js, md
```

```python
# evals/run.py
"""python -m evals.run --suite smoke|full --out reports/<dir>"""

import argparse
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from evals.report import MetricResult, write_report

# Suites register here as milestones add them (M1: knockout, requirements; M2: discover; M3: draft).
SUITES: dict[str, Callable[[], list[MetricResult]]] = {}
SMOKE: tuple[str, ...] = ()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", choices=["smoke", "full"], default="smoke")
    parser.add_argument("--out", default="reports/local")
    args = parser.parse_args(argv)
    names = SMOKE if args.suite == "smoke" else tuple(SUITES)
    results = [r for name in names for r in SUITES[name]()]
    run_id = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    _, md = write_report(results, Path(args.out), run_id)
    print(md.read_text(encoding="utf-8"))
    return 1 if any(r.passed is False for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_metrics.py tests/unit/test_eval_report.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Labeling guide and data folders**

Write `evals/LABELING.md` with these sections, in full sentences:
1. **Purpose and rule zero.** Golden sets are labeled by hand, frozen once written, and never used for tuning prompts or thresholds. Iteration happens on `evals/data/dev/`.
2. **Knockout verdicts for Lumen Grid Labs.** `INELIGIBLE` means at least one clause rules the company out, using the facts in `data/company/profile.json`. `NEEDS_REVIEW` means a clause exists that can't be decided from the profile (e.g. cost share, "must have prior DOE funding" without specifics). `ELIGIBLE` means no disqualifying clause was found after reading the eligibility section and every attachment. Record the clause quote verbatim, with document name and page.
3. **What counts as a knockout.** Entity type, size standard, ownership/control, location, registration (SAM/UEI), program phase prerequisites. Cost share and page limits are not knockouts.
4. **Requirements set.** A requirement is a "shall/must/will" statement the proposer must satisfy. One row per statement, quote verbatim, and skip boilerplate about the agency's own obligations.
5. **Discover relevance grades.** 2 means a strong fit to a stated capability; 1 means plausible but adjacent; 0 means not a fit.
6. **Draft evidence labels.** For each section prompt, list the company chunk files and headings that contain supporting evidence, and the requirements with no evidence (expected gaps).
7. **Sampling.** Stratify by source (Grants.gov vs. SAM.gov) and agency. Include at least 10 known knockouts in the knockout set. Record the sampling query and date.
8. **File formats.** JSONL, one object per line, with the field names listed in system-design §11.

Write `evals/data/golden/README.md` ("Hand-labeled, frozen. Do not tune on these. Files are added in M1–M3; see ../../LABELING.md.") and `evals/data/dev/README.md` ("LLM-assisted, human-reviewed labels for iteration and threshold tuning.").

- [ ] **Step 6: Commit**

```bash
git add evals tests/unit/test_metrics.py tests/unit/test_eval_report.py
git commit -m "feat(m0): eval harness skeleton, metrics and labeling guide

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 11: Architecture decision records

**Files:**
- Create: `docs/adr/0000-template.md`, `docs/adr/0001-…` through `0009-…`, `0012-…` through `0015-…`, `docs/adr/README.md`

**Interfaces:**
- Produces: decision records that the README and design doc link to. ADR-0010 and ADR-0011 are written in M5, after their experiments.

- [ ] **Step 1: Template**

```markdown
# ADR-NNNN: Title

- Status: Accepted | Proposed | Superseded by ADR-XXXX
- Date: YYYY-MM-DD
- Deciders: Karthick Balaje

## Context
What forces are at play: requirements, constraints, facts measured so far.

## Decision
The choice, in one or two sentences.

## Alternatives considered
- Option: why it was not chosen.

## Consequences
What becomes easier, what becomes harder, and what we will watch.
```

- [ ] **Step 2: Write each ADR from this table.** Use status Accepted and date 2026-10-07 unless noted. Each one is 150–300 words.

| ADR | Title | Context | Decision | Alternatives (why not) | Consequences |
|---|---|---|---|---|---|
| 0001 | Rebuild from scratch | The v0 prototype had prompt-only logic and no evals or tests; 2 of 3 modules were missing | New layout; v0 kept in `legacy/` and tag `v0-besi-prototype` | Incremental refactor (every module changes; refactoring would cost more than rewriting) | Clean contracts; v0 → v1 comparison is available for the write-up |
| 0002 | ADK 2 workflow graphs | PEV needs a loop, branches and resumable human approval | Google ADK 2.x workflows on Agent Runtime | LangGraph (strong, but outside the Google Cloud managed stack); ADK 1 `LoopAgent` (being phased out) | Typed state in sessions; tied to ADK release cadence |
| 0003 | Postgres + pgvector | Need metadata filters, full-text and vectors together, at a small scale (~20k pages) | Cloud SQL Postgres 16 + pgvector; hybrid search in one SQL query | AlloyDB (ScaNN, but the minimum size costs far more than the budget); Vector Search (separate system to keep in sync); RAG Engine (hides the retrieval stages); all three are compared in M5 | Cheap and transparent; we tune HNSW ourselves |
| 0004 | Docling for parsing | Solicitations are long, table-heavy PDFs; citations need page numbers | Docling with structure (headings, tables, pages) | Document AI Layout Parser (per-page cost); plain text extraction (loses structure) | Gemini multimodal fallback evaluated in M5 (ADR-0011) |
| 0005 | Embeddings | `gemini-embedding-2` returned 404 for the project on 2026-10-07; `gemini-embedding-001` works at 768-d in us-central1 | `gemini-embedding-001`, 768-d | 3072-d (larger index, quality gain unproven); `text-embedding-005` (older) | Re-test embedding-2 in M2 on the retrieval eval |
| 0006 | LLM extracts, rules decide | Eligibility mistakes cost a whole proposal; LLM judgements aren't auditable | Model extracts quoted clauses; Python rules decide; unparsed → NEEDS_REVIEW | LLM-judged eligibility (opaque, non-deterministic) | Rules need maintenance per clause category; recall is measured |
| 0007 | Offline index + live fallback | Live API search is slow and changes between runs, which breaks reproducible evals | Nightly ingestion into Postgres; live calls only for same-day postings | Live per-query calls (v0) | Data can be up to 24 h stale; ingestion becomes a job to operate |
| 0008 | Demo access | Public demo, single user, cost cap | Shared access code + 30 runs/day cap | IAP (adds friction for reviewers); multi-tenant auth (out of scope) | Not suitable for real customers, as documented |
| 0009 | Single prod project | Budget of $10/month | One project; CI deploys to a `-preview` Agent Runtime instance before promotion | Separate staging project (doubles fixed costs) | Less isolation, mitigated by preview deploys and the eval gate |
| 0012 | Runtime choice | Agents need managed sessions; API/UI/ingestion are plain containers | Agent Runtime for agents; Cloud Run for API, UI and ingestion job | Cloud Run for everything (lose managed sessions/memory); GKE (operational overhead) | Two deployment paths to maintain |
| 0013 | Analyze as an A2A service (Proposed; decided in M2) | Analyze is reused by Discover, Draft and external callers | Deploy Analyze separately and call it over A2A | Single deployment (simpler, but couples scaling and releases) | Network hop and auth between agents; independent versioning |
| 0014 | Per-agent identity (Proposed; decided in M4) | Least privilege; one leaked agent shouldn't reach everything | Agent Identity per agent with principal access boundary policies | One shared service account | More IAM to manage; clearer audit trail |
| 0015 | Sources and normalized format | SBIR.gov search API returns 403 and DSIP blocks access (tested 2026-10-07); SAM.gov API allows ~10 requests/day but SAM publishes a free daily CSV with descriptions; Simpler Grants serves CommonGrants natively | Index Grants.gov (API) + SAM.gov (daily CSV); SAM API only for on-demand attachments; USAspending, NIH RePORTER, NSF live and SBIR award CSV as context; export validated against the CommonGrants SDK | SAM API for bulk (quota); scraping SBIR.gov/DSIP (fragile, against terms); a source-specific schema | One 210 MB daily download; SAM attachments arrive later (on demand) than Grants.gov ones |

- [ ] **Step 3: Index**

`docs/adr/README.md`: a table of number, title and status linking every file, plus one sentence explaining what an ADR is.

- [ ] **Step 4: Commit**

```bash
git add docs/adr
git commit -m "docs(m0): architecture decision records 0001-0009 and 0012-0015

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 12: CI workflow

**Files:**
- Create: `.github/workflows/ci.yml`

**Interfaces:**
- Consumes: `tests/unit`, `tests/db`, `python -m evals.run`, lint config from Task 2.

- [ ] **Step 1: Write the workflow**

```yaml
# .github/workflows/ci.yml
name: CI

on:
  pull_request:
    branches: [main]
  push:
    branches: [main]

jobs:
  checks:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: pgvector/pgvector:pg16
        env:
          POSTGRES_USER: grant
          POSTGRES_PASSWORD: grant
          POSTGRES_DB: grant_capture_test
        ports: ["5433:5432"]
        options: >-
          --health-cmd "pg_isready -U grant"
          --health-interval 5s --health-timeout 5s --health-retries 10
    env:
      TEST_DATABASE_URL: postgresql+psycopg://grant:grant@localhost:5433/grant_capture_test
      DATABASE_URL: postgresql+psycopg://grant:grant@localhost:5433/grant_capture_test
      REQUIRE_DB: "1"
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v8.0.0
        with:
          python-version: "3.12"
      - run: uv sync --locked --extra lint
      - name: Lint
        run: |
          uv run ruff check .
          uv run ruff format --check .
          uv run codespell --skip "uv.lock,*.json,legacy/*"
      - name: Type check
        run: uv run ty check app ingest db evals
      - name: Unit and database tests
        run: uv run pytest tests/unit tests/db -q
      - name: Eval smoke
        run: uv run python -m evals.run --suite smoke --out reports/ci
      - uses: actions/upload-artifact@v4
        if: always()
        with:
          name: eval-report
          path: reports/ci
```

- [ ] **Step 2: Verify locally that each command passes**

Run each command from the workflow locally (with `docker compose up -d db` and `TEST_DATABASE_URL` pointing at port 5433).
Expected: all succeed. Fix any `ruff` or `ty` findings in our code; don't add blanket ignores.

- [ ] **Step 3: Commit and open the M0 PR to see CI run**

```bash
git add .github/workflows/ci.yml
git commit -m "ci(m0): lint, type check, unit + db tests and eval smoke

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push -u origin m0-foundation
GH_TOKEN=$(gh auth token --user kb2326) gh pr create --repo kb2326/grant-capture-agent \
  --base main --head m0-foundation --draft --title "M0 Foundation" \
  --body "Tracks docs/plans/2026-10-07-m0-foundation.md"
```
Expected: the `CI / checks` job is green on the draft PR.

---

### Task 13: Local acceptance run

**Files:**
- Modify: `README.md` (Getting started)

- [ ] **Step 1: Ingest at least 1,000 opportunities with attachments**

```bash
docker compose up -d db
uv run alembic upgrade head
uv run python -m ingest seed-company
uv run python -m ingest run --source grants_gov --limit 1200   # ~25 min at 60 req/min
uv run python -m ingest run --source sam_gov
uv run python -m ingest stats
```
Expected: `stats` shows at least 1,000 opportunities across both sources (Grants.gov had 1,458 open/forecasted on 2026-10-07), at least 300 opportunities with documents (Grants.gov attachments; SAM attachments are fetched on demand from M1), and an error count below 5% of `seen`. Record the actual numbers in the PR description. (The SAM run reads the daily bulk file and uses none of the API quota.)

- [ ] **Step 1b: Check the raw zone, provenance and quality report**

```bash
ls data/blobs/raw/api/grants_gov/$(date +%F) | head      # search pages + detail JSONs
uv run python -c "
from sqlalchemy import select; from app.config import get_settings
from db.models import IngestRunRow, OpportunityRow; from db.session import make_engine, make_session_factory
with make_session_factory(make_engine(get_settings().database_url))() as s:
    r=s.scalars(select(OpportunityRow).limit(1)).one(); print(r.adapter_version, r.fetched_at, r.raw_uri)
    for run in s.scalars(select(IngestRunRow).order_by(IngestRunRow.started_at)): print(run.stats['source'], run.stats.get('quality_issues'))"
uv run python -m ingest replay --source grants_gov --date $(date +%F)
```
Expected: the raw files exist, every row has provenance, the full runs show no `error` issues, and the replay reports `unchanged` equal to `seen` (the same files map to the same records).

- [ ] **Step 2: Re-run to prove idempotence on real data**

Run: `uv run python -m ingest run --source grants_gov --limit 200`
Expected: `new` is 0 or close to it (only opportunities posted since the first run); `attachments_stored` is close to 0.

- [ ] **Step 3: Update README "Getting started"**

Replace the README's Getting started section with:

````markdown
## Getting started

Requirements: [uv](https://docs.astral.sh/uv/), Docker, [agents-cli](https://google.github.io/agents-cli/) 1.9+, and free API keys for [Simpler Grants](https://simpler.grants.gov/) and [SAM.gov](https://sam.gov/).

```bash
cp .env.example .env            # add SIMPLER_GRANTS_API_KEY and SAM_API_KEY
docker compose up -d db         # Postgres 16 + pgvector on localhost:5433
uv sync
uv run alembic upgrade head
uv run python -m ingest seed-company
uv run python -m ingest run --source grants_gov --limit 200
uv run python -m ingest stats
uv run pytest tests/unit tests/db
agents-cli playground           # chat with the agent locally
```
````

- [ ] **Step 4: Commit**

```bash
git add README.md
git commit -m "docs(m0): getting started

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

# Part B: Cloud foundation

**Prerequisite:** Terraform ≥ 1.9 installed (`winget install --id Hashicorp.Terraform -e`), `gcloud` and ADC signed in as `karthickbalaje01@gmail.com` with project `grant-capture-agent`.

### Task 14: Terraform state bucket and foundation module

**Files:**
- Create: `scripts/bootstrap_tf_state.sh`, `deployment/terraform/foundation/{versions.tf,variables.tf,main.tf,iam.tf,cloudsql.tf,outputs.tf,terraform.tfvars}`

**Interfaces:**
- Produces (Terraform outputs): `raw_bucket`, `artifact_repo`, `cloudsql_connection_name`, `cloudsql_instance`, `ingest_sa_email`, `agent_sa_email`, `api_sa_email`, `ci_sa_email`, `wif_provider`, and the secret IDs `simpler-grants-api-key`, `sam-api-key`, `db-app-password`.

- [ ] **Step 1: State bucket (one-time; Terraform can't create its own backend)**

```bash
# scripts/bootstrap_tf_state.sh
set -euo pipefail
PROJECT=grant-capture-agent
BUCKET=gs://${PROJECT}-tfstate
gcloud storage buckets describe "$BUCKET" >/dev/null 2>&1 || \
  gcloud storage buckets create "$BUCKET" --project "$PROJECT" --location us-central1 \
    --uniform-bucket-level-access --public-access-prevention
gcloud storage buckets update "$BUCKET" --versioning
echo "state bucket ready: $BUCKET"
```
Run: `bash scripts/bootstrap_tf_state.sh`
Expected: `state bucket ready: gs://grant-capture-agent-tfstate`.

- [ ] **Step 2: Foundation module**

```hcl
# deployment/terraform/foundation/versions.tf
terraform {
  required_version = ">= 1.9"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.0" }
    random = { source = "hashicorp/random", version = "~> 3.6" }
  }
  backend "gcs" {
    bucket = "grant-capture-agent-tfstate"
    prefix = "foundation"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}
```

```hcl
# deployment/terraform/foundation/variables.tf
variable "project_id" { type = string }
variable "region" {
  type    = string
  default = "us-central1"
}
variable "github_repository" {
  type        = string
  description = "owner/repo allowed to use Workload Identity Federation"
}
variable "db_tier" {
  type    = string
  default = "db-f1-micro"
}
variable "enable_cloudsql" {
  type        = bool
  default     = true
  description = "false deletes the instance between work sessions (a stopped instance still pays for its IPv4 address)"
}
variable "db_activation_policy" {
  type        = string
  default     = "ALWAYS"
  description = "Initial policy only; the instance must be running for Terraform to create the database and user. scripts/cloudsql.sh toggles it afterwards."
}
```

```hcl
# deployment/terraform/foundation/terraform.tfvars
project_id        = "grant-capture-agent"
github_repository = "kb2326/grant-capture-agent"
```

```hcl
# deployment/terraform/foundation/main.tf
locals {
  services = [
    "aiplatform.googleapis.com", "artifactregistry.googleapis.com", "cloudbuild.googleapis.com",
    "iam.googleapis.com", "iamcredentials.googleapis.com", "run.googleapis.com",
    "secretmanager.googleapis.com", "sqladmin.googleapis.com", "storage.googleapis.com",
    "sts.googleapis.com", "cloudscheduler.googleapis.com", "logging.googleapis.com",
    "cloudtrace.googleapis.com", "discoveryengine.googleapis.com",
  ]
}

resource "google_project_service" "enabled" {
  for_each           = toset(local.services)
  service            = each.value
  disable_on_destroy = false
}

resource "google_storage_bucket" "raw" {
  name                        = "${var.project_id}-raw"
  location                    = var.region
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  versioning { enabled = false }
  lifecycle_rule {
    condition {
      age            = 30
      matches_prefix = ["raw/api/sam_gov/"] # the 210 MB daily SAM extract; keep 30 days for replay
    }
    action { type = "Delete" }
  }
  lifecycle_rule {
    condition { age = 365 }
    action {
      type          = "SetStorageClass"
      storage_class = "NEARLINE"
    }
  }
  depends_on = [google_project_service.enabled]
}

resource "google_artifact_registry_repository" "containers" {
  repository_id = "grant-capture"
  location      = var.region
  format        = "DOCKER"
  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions { keep_count = 5 }
  }
  depends_on = [google_project_service.enabled]
}

resource "google_secret_manager_secret" "secrets" {
  for_each  = toset(["simpler-grants-api-key", "sam-api-key", "db-app-password"])
  secret_id = each.value
  replication {
    auto {}
  }
  depends_on = [google_project_service.enabled]
}
```

```hcl
# deployment/terraform/foundation/cloudsql.tf
resource "random_password" "db_app" {
  length  = 32
  special = false
}

resource "google_sql_database_instance" "main" {
  count            = var.enable_cloudsql ? 1 : 0
  name             = "grant-capture-pg"
  database_version = "POSTGRES_16"
  region           = var.region
  settings {
    tier              = var.db_tier
    edition           = "ENTERPRISE"
    activation_policy = var.db_activation_policy
    disk_type         = "PD_HDD"
    disk_size         = 10
    disk_autoresize   = false
    availability_type = "ZONAL"
    backup_configuration { enabled = false }
    ip_configuration {
      ipv4_enabled = true # no authorized networks; access only via Cloud SQL connectors/proxy with IAM
      ssl_mode     = "ENCRYPTED_ONLY"
    }
    database_flags {
      name  = "cloudsql.iam_authentication"
      value = "on"
    }
  }
  deletion_protection = false # recreated on demand; data is rebuilt by re-running ingestion
  depends_on          = [google_project_service.enabled]
  lifecycle {
    ignore_changes = [settings[0].activation_policy] # toggled by scripts/cloudsql.sh
  }
}

resource "google_sql_database" "app" {
  count    = var.enable_cloudsql ? 1 : 0
  name     = "grant_capture"
  instance = google_sql_database_instance.main[0].name
}

resource "google_sql_user" "app" {
  count    = var.enable_cloudsql ? 1 : 0
  name     = "grant_app"
  instance = google_sql_database_instance.main[0].name
  password = random_password.db_app.result
}

resource "google_secret_manager_secret_version" "db_app_password" {
  secret      = google_secret_manager_secret.secrets["db-app-password"].id
  secret_data = random_password.db_app.result
}
```

```hcl
# deployment/terraform/foundation/iam.tf
locals {
  sas = {
    ingest = "Ingestion job: writes raw files and DB rows"
    agent  = "ADK agents on Agent Runtime: reads DB, calls Gemini"
    api    = "FastAPI backend on Cloud Run"
    ci     = "GitHub Actions via Workload Identity Federation"
  }
}

resource "google_service_account" "sa" {
  for_each     = local.sas
  account_id   = "gca-${each.key}"
  display_name = "grant-capture ${each.key}"
  description  = each.value
}

# Ingestion: Cloud SQL client, write raw bucket, read source-API and DB secrets
resource "google_project_iam_member" "ingest_sql" {
  project = var.project_id
  role    = "roles/cloudsql.client"
  member  = "serviceAccount:${google_service_account.sa["ingest"].email}"
}
resource "google_storage_bucket_iam_member" "ingest_raw" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.sa["ingest"].email}"
}
resource "google_secret_manager_secret_iam_member" "ingest_secrets" {
  for_each  = toset(["simpler-grants-api-key", "sam-api-key", "db-app-password"])
  secret_id = google_secret_manager_secret.secrets[each.value].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.sa["ingest"].email}"
}

# Agents: Gemini + Cloud SQL client + read raw bucket + DB password
resource "google_project_iam_member" "agent_roles" {
  for_each = toset(["roles/aiplatform.user", "roles/cloudsql.client"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.sa["agent"].email}"
}
resource "google_storage_bucket_iam_member" "agent_raw_read" {
  bucket = google_storage_bucket.raw.name
  role   = "roles/storage.objectViewer"
  member = "serviceAccount:${google_service_account.sa["agent"].email}"
}
resource "google_secret_manager_secret_iam_member" "agent_db_secret" {
  secret_id = google_secret_manager_secret.secrets["db-app-password"].id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.sa["agent"].email}"
}

# CI: push images and run the ingestion job; nothing else in M0
resource "google_artifact_registry_repository_iam_member" "ci_push" {
  repository = google_artifact_registry_repository.containers.name
  location   = var.region
  role       = "roles/artifactregistry.writer"
  member     = "serviceAccount:${google_service_account.sa["ci"].email}"
}

resource "google_iam_workload_identity_pool" "github" {
  workload_identity_pool_id = "github"
  display_name              = "GitHub Actions"
}

resource "google_iam_workload_identity_pool_provider" "github" {
  workload_identity_pool_id          = google_iam_workload_identity_pool.github.workload_identity_pool_id
  workload_identity_pool_provider_id = "github-oidc"
  attribute_mapping = {
    "google.subject"       = "assertion.sub"
    "attribute.repository" = "assertion.repository"
    "attribute.ref"        = "assertion.ref"
  }
  attribute_condition = "assertion.repository == \"${var.github_repository}\""
  oidc { issuer_uri = "https://token.actions.githubusercontent.com" }
}

resource "google_service_account_iam_member" "ci_wif" {
  service_account_id = google_service_account.sa["ci"].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "principalSet://iam.googleapis.com/${google_iam_workload_identity_pool.github.name}/attribute.repository/${var.github_repository}"
}
```

```hcl
# deployment/terraform/foundation/outputs.tf
output "raw_bucket" { value = google_storage_bucket.raw.name }
output "artifact_repo" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.containers.repository_id}"
}
output "cloudsql_instance" { value = one(google_sql_database_instance.main[*].name) }
output "cloudsql_connection_name" { value = one(google_sql_database_instance.main[*].connection_name) }
output "ingest_sa_email" { value = google_service_account.sa["ingest"].email }
output "agent_sa_email" { value = google_service_account.sa["agent"].email }
output "api_sa_email" { value = google_service_account.sa["api"].email }
output "ci_sa_email" { value = google_service_account.sa["ci"].email }
output "wif_provider" { value = google_iam_workload_identity_pool_provider.github.name }
```

- [ ] **Step 3: Plan and review**

```bash
cd deployment/terraform/foundation
terraform init
terraform fmt -check && terraform validate
terraform plan -out tfplan
```
Expected: about 40 resources to add and 0 to destroy. Read the plan. Check that no resource is public and that the Cloud SQL tier is `db-f1-micro`.

- [ ] **Step 4: Apply**

Run: `terraform apply tfplan`
Expected: `Apply complete!` (Cloud SQL creation takes 5–10 minutes). Run `terraform output` and keep the values for the next tasks. Then stop the instance until Task 15 needs it: `gcloud sql instances patch grant-capture-pg --activation-policy NEVER --quiet` (Task 15 wraps this in `scripts/cloudsql.sh`).

- [ ] **Step 5: Commit**

```bash
cd -
git add scripts/bootstrap_tf_state.sh deployment/terraform/foundation/*.tf deployment/terraform/foundation/terraform.tfvars deployment/terraform/foundation/.terraform.lock.hcl
git commit -m "infra(m0): Terraform foundation - GCS, Artifact Registry, Secret Manager, Cloud SQL+pgvector, SAs, WIF

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 15: Secrets, Cloud SQL helper scripts and cloud migration

**Files:**
- Create: `scripts/secrets_put.sh`, `scripts/cloudsql.sh`
- Modify: `app/config.py` (Secret Manager fallback), `tests/unit/test_config.py`

**Interfaces:**
- Produces: `app.config.load_secret(secret_id: str, project: str, client=None) -> str | None`; `Settings` resolves `simpler_grants_api_key`/`sam_api_key` from Secret Manager when the env var is empty and `USE_SECRET_MANAGER=1`.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/unit/test_config.py
from app.config import load_secret


class _FakeSM:
    def __init__(self, value):
        self.value, self.calls = value, []

    def access_secret_version(self, name):
        self.calls.append(name)
        if self.value is None:
            raise KeyError(name)

        class R:
            pass

        r = R()
        r.payload = R()
        r.payload.data = self.value.encode()
        return r


def test_load_secret_reads_latest_version():
    sm = _FakeSM("s3cret")
    assert load_secret("sam-api-key", "grant-capture-agent", client=sm) == "s3cret"
    assert sm.calls == ["projects/grant-capture-agent/secrets/sam-api-key/versions/latest"]


def test_load_secret_missing_returns_none():
    assert load_secret("nope", "p", client=_FakeSM(None)) is None
```

- [ ] **Step 2: Run to see it fail**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: FAIL with `ImportError: cannot import name 'load_secret'`.

- [ ] **Step 3: Implement in `app/config.py`**

```python
import os

from pydantic import model_validator


def load_secret(secret_id: str, project: str, client=None) -> str | None:
    if client is None:
        from google.cloud import secretmanager

        client = secretmanager.SecretManagerServiceClient()
    try:
        response = client.access_secret_version(
            name=f"projects/{project}/secrets/{secret_id}/versions/latest")
    except Exception:
        return None
    return response.payload.data.decode("utf-8")
```
And inside `Settings`, add:

```python
    @model_validator(mode="after")
    def _secrets_from_secret_manager(self) -> "Settings":
        if os.environ.get("USE_SECRET_MANAGER") != "1":
            return self
        for field, secret_id in (("simpler_grants_api_key", "simpler-grants-api-key"),
                                 ("sam_api_key", "sam-api-key")):
            if getattr(self, field) is None:
                value = load_secret(secret_id, self.google_cloud_project)
                if value:
                    object.__setattr__(self, field, SecretStr(value))
        return self
```

- [ ] **Step 4: Run tests**

Run: `uv run pytest tests/unit/test_config.py -v`
Expected: 4 PASS.

- [ ] **Step 5: Helper scripts**

```bash
# scripts/secrets_put.sh  — copies keys from .env into Secret Manager (never echoes them)
set -euo pipefail
PROJECT=grant-capture-agent
set -a; source .env; set +a
put() { printf '%s' "$2" | gcloud secrets versions add "$1" --project "$PROJECT" --data-file=- >/dev/null && echo "updated $1"; }
[ -n "${SIMPLER_GRANTS_API_KEY:-}" ] && put simpler-grants-api-key "$SIMPLER_GRANTS_API_KEY"
[ -n "${SAM_API_KEY:-}" ] && put sam-api-key "$SAM_API_KEY"
```

```bash
# scripts/cloudsql.sh  — up | down | status | proxy
set -euo pipefail
PROJECT=grant-capture-agent; INSTANCE=grant-capture-pg; REGION=us-central1
case "${1:-status}" in
  up)     gcloud sql instances patch "$INSTANCE" --project "$PROJECT" --activation-policy ALWAYS --quiet ;;
  down)   gcloud sql instances patch "$INSTANCE" --project "$PROJECT" --activation-policy NEVER --quiet ;;
  status) gcloud sql instances describe "$INSTANCE" --project "$PROJECT" --format "value(state,settings.activationPolicy)" ;;
  proxy)  cloud-sql-proxy "$PROJECT:$REGION:$INSTANCE" --port 5434 ;;
  *) echo "usage: $0 up|down|status|proxy"; exit 2 ;;
esac
```
Terraform ignores `activation_policy` after creation (the `lifecycle` block in `cloudsql.tf`), so the script and `terraform apply` don't fight.

- [ ] **Step 6: Push secrets, start the DB, migrate, enable pgvector**

```bash
bash scripts/secrets_put.sh
bash scripts/cloudsql.sh up            # ~2 min; billing starts
gcloud components install cloud-sql-proxy --quiet   # once (or download the binary)
bash scripts/cloudsql.sh proxy &       # localhost:5434 → Cloud SQL
export DATABASE_URL="postgresql+psycopg://grant_app:$(gcloud secrets versions access latest --secret db-app-password)@localhost:5434/grant_capture"
uv run alembic upgrade head
```
Expected: `Running upgrade  -> 0001, initial schema` against Cloud SQL. The migration's `CREATE EXTENSION vector` succeeds because Cloud SQL Postgres supports pgvector. If it fails with a permission error, run it once as the `postgres` user from Cloud SQL Studio, then re-run the migration.

- [ ] **Step 7: Commit**

```bash
git add app/config.py tests/unit/test_config.py scripts/secrets_put.sh scripts/cloudsql.sh
git commit -m "infra(m0): Secret Manager config fallback, Cloud SQL helpers, cloud migration

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 16: Ingestion as a Cloud Run Job

**Files:**
- Create: `Dockerfile.ingest`, `cloudbuild.ingest.yaml`, `deployment/terraform/foundation/ingest_job.tf`
- Modify: `deployment/terraform/foundation/outputs.tf`

**Interfaces:**
- Consumes: the CLI from Task 8, `USE_SECRET_MANAGER`, `BLOB_ROOT=gs://grant-capture-agent-raw`, and the Cloud SQL unix socket.
- Produces: Cloud Run Job `grant-capture-ingest` and Cloud Scheduler job `grant-capture-ingest-nightly` (**paused** until M2).

- [ ] **Step 1: Container**

```dockerfile
# Dockerfile.ingest
FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project
COPY app ./app
COPY ingest ./ingest
COPY db ./db
COPY evals ./evals
COPY data/company/profile.json ./data/company/profile.json
COPY alembic.ini ./
RUN uv sync --locked --no-dev
ENV PYTHONUNBUFFERED=1 USE_SECRET_MANAGER=1
ENTRYPOINT ["uv", "run", "--no-dev", "python", "-m", "ingest"]
```
Build and push with Cloud Build (no local Docker push needed):

```yaml
# cloudbuild.ingest.yaml
steps:
  - name: gcr.io/cloud-builders/docker
    args: ["build", "-f", "Dockerfile.ingest", "-t", "${_IMAGE}", "."]
images: ["${_IMAGE}"]
```

```bash
REPO=$(terraform -chdir=deployment/terraform/foundation output -raw artifact_repo)
gcloud builds submit --project grant-capture-agent --region us-central1 \
  --config cloudbuild.ingest.yaml --substitutions "_IMAGE=$REPO/ingest:m0" .
```
Expected: `SUCCESS` and the image `…/grant-capture/ingest:m0`.

- [ ] **Step 2: Job and paused schedule**

```hcl
# deployment/terraform/foundation/ingest_job.tf
variable "ingest_image" {
  type    = string
  default = "us-central1-docker.pkg.dev/grant-capture-agent/grant-capture/ingest:m0"
}

resource "google_cloud_run_v2_job" "ingest" {
  count    = var.enable_cloudsql ? 1 : 0
  name     = "grant-capture-ingest"
  location = var.region
  template {
    task_count = 1
    template {
      service_account = google_service_account.sa["ingest"].email
      timeout         = "3600s"
      max_retries     = 0
      volumes {
        name = "cloudsql"
        cloud_sql_instance { instances = [google_sql_database_instance.main[0].connection_name] }
      }
      containers {
        image = var.ingest_image
        args  = ["run", "--source", "grants_gov", "--limit", "500"] # M2 adds a sam_gov job
        resources { limits = { cpu = "1", memory = "1Gi" } }
        env {
          name  = "GOOGLE_CLOUD_PROJECT"
          value = var.project_id
        }
        env {
          name  = "BLOB_ROOT"
          value = "gs://${google_storage_bucket.raw.name}"
        }
        env {
          name = "DB_PASSWORD"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.secrets["db-app-password"].secret_id
              version = "latest"
            }
          }
        }
        env {
          name  = "DATABASE_URL"
          value = "postgresql+psycopg://grant_app:$(DB_PASSWORD)@/grant_capture?host=/cloudsql/${google_sql_database_instance.main[0].connection_name}"
        }
        volume_mounts {
          name       = "cloudsql"
          mount_path = "/cloudsql"
        }
      }
    }
  }
  depends_on = [google_project_service.enabled]
}

resource "google_cloud_scheduler_job" "ingest_nightly" {
  count    = var.enable_cloudsql ? 1 : 0
  name      = "grant-capture-ingest-nightly"
  region    = var.region
  schedule  = "0 2 * * *"
  time_zone = "America/Chicago"
  paused    = true # enabled in M2 once Discover needs fresh data
  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${google_cloud_run_v2_job.ingest[0].name}:run"
    oauth_token { service_account_email = google_service_account.sa["ingest"].email }
  }
}

resource "google_cloud_run_v2_job_iam_member" "ingest_self_invoke" {
  count    = var.enable_cloudsql ? 1 : 0
  name     = google_cloud_run_v2_job.ingest[0].name
  location = var.region
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.sa["ingest"].email}"
}
```
Cloud Run doesn't expand `$(DB_PASSWORD)` inside another variable's value. So also add this to `app/config.py`'s `Settings` validator: if `DB_PASSWORD` is set and `database_url` contains the literal `$(DB_PASSWORD)`, substitute it. Add a unit test:

```python
def test_db_password_placeholder_is_substituted(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql+psycopg://u:$(DB_PASSWORD)@/d?host=/cloudsql/x")
    monkeypatch.setenv("DB_PASSWORD", "pw")
    assert Settings(_env_file=None).database_url == "postgresql+psycopg://u:pw@/d?host=/cloudsql/x"
```
Implement it inside `_secrets_from_secret_manager`, before the `USE_SECRET_MANAGER` check:

```python
        password = os.environ.get("DB_PASSWORD")
        if password and "$(DB_PASSWORD)" in self.database_url:
            object.__setattr__(self, "database_url", self.database_url.replace("$(DB_PASSWORD)", password))
```
Add to `outputs.tf`: `output "ingest_job" { value = one(google_cloud_run_v2_job.ingest[*].name) }`.

- [ ] **Step 3: Apply and execute once**

```bash
uv run pytest tests/unit/test_config.py -v            # 5 PASS
terraform -chdir=deployment/terraform/foundation apply
bash scripts/cloudsql.sh up
gcloud run jobs execute grant-capture-ingest --region us-central1 --project grant-capture-agent --wait
```
Expected: the execution succeeds. Its logs end with the stats JSON, including `"new": 500` or fewer, and GCS lists the files:

```bash
gcloud storage ls gs://grant-capture-agent-raw/raw/grants_gov/ | head
```

- [ ] **Step 4: Remove the database until it's needed again**

A stopped instance still pays for its IPv4 address (about $7/month), which is most of the $10 budget. So after this verification, delete it. The ingestion data is reproducible by re-running the job.

```bash
terraform -chdir=deployment/terraform/foundation apply -var enable_cloudsql=false
```
Expected: the plan destroys the Cloud SQL instance, database, user, ingestion job and schedule, and keeps everything else (buckets, secrets, service accounts, WIF, Artifact Registry). M2 recreates them with `-var enable_cloudsql=true`.

- [ ] **Step 5: Commit**

```bash
git add Dockerfile.ingest cloudbuild.ingest.yaml deployment/terraform/foundation/ingest_job.tf deployment/terraform/foundation/outputs.tf app/config.py tests/unit/test_config.py
git commit -m "infra(m0): ingestion Cloud Run Job on Cloud SQL + GCS, nightly schedule (paused)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 17: M0 close-out

**Files:**
- Modify: `docs/guide/project-guide.html` (status pills, decision log), `README.md` (roadmap checkbox), `CLAUDE.md` (cloud commands)

- [ ] **Step 1: Verify every M0 acceptance criterion** (system-design §17), with evidence:

| Criterion | Evidence command |
|---|---|
| Scaffold in place | `agents-cli info` shows `agent_directory: app` |
| Company data written | `uv run pytest tests/unit/test_company_docs.py` |
| Schema migrated (local + Cloud SQL) | `uv run alembic current` on both URLs shows `0001 (head)` |
| ≥ 1,000 opportunities with attachments | `uv run python -m ingest stats` (local) |
| CI runs lint, types and tests | green `CI / checks` on the M0 PR |
| Eval harness runs an empty report | `uv run python -m evals.run --suite smoke` |
| ADRs written | `ls docs/adr` shows 0001–0009, 0012–0015 |
| Coding-agent conventions | `CLAUDE.md`, `AGENTS.md`, `.pre-commit-config.yaml` present |
| Raw zone, provenance, replay | Task 13 Step 1b output |
| Data-quality checks | `ingest_runs.stats.quality_issues` present on full runs; no errors |
| Cloud foundation | `terraform -chdir=deployment/terraform/foundation plan -var enable_cloudsql=false` shows no changes |
| Cloud ingestion | the last `gcloud run jobs executions list --job grant-capture-ingest` shows success |

- [ ] **Step 2: Update docs**

- README roadmap: tick M0.
- Guide: set the "Evals first" and "Implementation plan" phases to done and M0 to done; add a decision-log row with the measured ingestion numbers.
- `CLAUDE.md`: add the cloud commands (`scripts/cloudsql.sh up|down|proxy`, `scripts/secrets_put.sh`, `gcloud run jobs execute grant-capture-ingest`).

- [ ] **Step 3: Commit, mark the PR ready, merge after CI is green**

```bash
git add README.md docs/guide/project-guide.html CLAUDE.md
git commit -m "docs(m0): close out M0 Foundation

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
git push
GH_TOKEN=$(gh auth token --user kb2326) gh pr ready --repo kb2326/grant-capture-agent m0-foundation
```
Confirm Cloud SQL is deleted (`gcloud sql instances list --project grant-capture-agent` is empty) before ending the session.
