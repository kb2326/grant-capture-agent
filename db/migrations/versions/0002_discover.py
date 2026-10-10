"""discover: opportunity cards and preferences

Revision ID: 0002
Revises: 0001
Create Date: 2026-10-09

"""

from collections.abc import Sequence

import pgvector.sqlalchemy
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "opportunity_cards",
        sa.Column("opportunity_id", sa.UUID(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("text_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "emb_gemini",
            pgvector.sqlalchemy.Vector(dim=768),
            nullable=True,
            comment="gemini-embedding-001, 768-d, RETRIEVAL_DOCUMENT",
        ),
        sa.Column(
            "emb_local",
            pgvector.sqlalchemy.Vector(dim=768),
            nullable=True,
            comment="google/embeddinggemma-2, 768-d, normalized",
        ),
        sa.Column(
            "tsv",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english', text)", persisted=True),
            nullable=True,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["opportunity_id"], ["opportunities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("opportunity_id"),
    )
    for col in ("emb_gemini", "emb_local"):
        op.create_index(
            f"ix_cards_{col}_hnsw",
            "opportunity_cards",
            [col],
            unique=False,
            postgresql_using="hnsw",
            postgresql_with={"m": 16, "ef_construction": 64},
            postgresql_ops={col: "vector_cosine_ops"},
        )
    op.create_index(
        "ix_cards_tsv",
        "opportunity_cards",
        ["tsv"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_table(
        "preferences",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("company_id", sa.UUID(), nullable=False),
        sa.Column("kind", sa.String(length=32), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "kind in ('exclude_agency','min_award_usd','avoid_topic','prefer_topic')",
            name="ck_preferences_kind",
        ),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("company_id", "kind", "value", name="uq_preferences_value"),
    )


def downgrade() -> None:
    op.drop_table("preferences")
    op.drop_index(
        "ix_cards_tsv", table_name="opportunity_cards", postgresql_using="gin"
    )
    for col in ("emb_gemini", "emb_local"):
        op.drop_index(
            f"ix_cards_{col}_hnsw",
            table_name="opportunity_cards",
            postgresql_using="hnsw",
        )
    op.drop_table("opportunity_cards")
