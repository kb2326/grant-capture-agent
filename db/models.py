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
        CheckConstraint(
            "kind in ('grant','sbir','sttr','contract')", name="ck_opportunities_kind"
        ),
        CheckConstraint(
            "status in ('forecasted','open','closed','custom')",
            name="ck_opportunities_status",
        ),
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
        CheckConstraint(
            "corpus in ('solicitation','company')", name="ck_documents_corpus"
        ),
        UniqueConstraint(
            "opportunity_id", "sha256", name="uq_documents_opportunity_sha"
        ),
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
        Computed(
            "to_tsvector('english', coalesce(section_path, '') || ' ' || text)",
            persisted=True,
        ),
    )


class CompanyRow(Base):
    __tablename__ = "companies"
    id: Mapped[uuid.UUID] = _uuid_pk()
    name: Mapped[str] = mapped_column(Text, unique=True)
    profile: Mapped[dict[str, Any]] = mapped_column(JSONB)


class SolicitationBriefRow(Base):
    __tablename__ = "solicitation_briefs"
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("opportunities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    brief: Mapped[dict[str, Any]] = mapped_column(JSONB)
    model: Mapped[str] = mapped_column(String(64))
    prompt_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = _now()


class EligibilityVerdictRow(Base):
    __tablename__ = "eligibility_verdicts"
    __table_args__ = (
        CheckConstraint(
            "verdict in ('ELIGIBLE','INELIGIBLE','NEEDS_REVIEW')",
            name="ck_verdicts_verdict",
        ),
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("opportunities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    verdict: Mapped[str] = mapped_column(String(16))
    detail: Mapped[dict[str, Any]] = mapped_column(JSONB)
    rules_version: Mapped[str] = mapped_column(String(32))
    created_at: Mapped[datetime] = _now()


class SavedOpportunityRow(Base):
    __tablename__ = "saved_opportunities"
    company_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        primary_key=True,
    )
    opportunity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("opportunities.id", ondelete="CASCADE"),
        primary_key=True,
    )
    status: Mapped[str] = mapped_column(String(32), default="pursuing")
    notes: Mapped[str] = mapped_column(Text, default="")
    updated_at: Mapped[datetime] = _now()


class DraftRow(Base):
    __tablename__ = "drafts"
    __table_args__ = (
        CheckConstraint(
            "status in ('pending_review','approved','rejected')",
            name="ck_drafts_status",
        ),
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
