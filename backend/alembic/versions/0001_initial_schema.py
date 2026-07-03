"""Initial schema — reviews and scrape_jobs tables with pgvector

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # ── reviews ──────────────────────────────────────────────────────
    op.create_table(
        "reviews",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "source",
            sa.Enum("play_store", "app_store", "reddit", name="reviewsource"),
            nullable=False,
        ),
        sa.Column("author", sa.String(255), nullable=True),
        sa.Column("rating", sa.Integer(), nullable=True),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("cleaned_content", sa.Text(), nullable=True),
        sa.Column("review_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "scraped_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("external_id", sa.String(255), nullable=True),
        # pgvector column — 1536 dims for text-embedding-3-small
        sa.Column("embedding", sa.Text(), nullable=True),  # placeholder
    )

    # Replace placeholder with real vector column
    op.execute("ALTER TABLE reviews DROP COLUMN embedding")
    op.execute("ALTER TABLE reviews ADD COLUMN embedding vector(1536)")

    op.create_unique_constraint("uq_reviews_content_hash", "reviews", ["content_hash"])
    op.create_index("ix_reviews_source", "reviews", ["source"])
    op.create_index("ix_reviews_source_date", "reviews", ["source", "review_date"])

    # HNSW index for fast approximate nearest-neighbour search
    op.execute(
        """
        CREATE INDEX ix_reviews_embedding_hnsw
        ON reviews
        USING hnsw (embedding vector_cosine_ops)
        WITH (m = 16, ef_construction = 64)
        """
    )

    # ── scrape_jobs ──────────────────────────────────────────────────
    op.create_table(
        "scrape_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("celery_task_id", sa.String(255), nullable=True, unique=True),
        sa.Column(
            "source",
            sa.Enum("play_store", "app_store", "reddit", name="reviewsource"),
            nullable=True,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "running", "completed", "failed", name="scrapejobstatus"),
            nullable=False,
        ),
        sa.Column("reviews_found", sa.Integer(), default=0),
        sa.Column("reviews_added", sa.Integer(), default=0),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("scrape_jobs")
    op.drop_table("reviews")
    op.execute("DROP TYPE IF EXISTS scrapejobstatus")
    op.execute("DROP TYPE IF EXISTS reviewsource")
    op.execute("DROP EXTENSION IF EXISTS vector")
