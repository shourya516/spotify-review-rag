"""
init_db.py — Programmatic schema bootstrap.

Usage (from the backend/ directory):
    python -m app.db.init_db

This is an alternative to running Alembic migrations and is useful for:
  - Integration tests that spin up a throwaway database
  - CI pipelines where you want a clean schema without migration history

For production use, always prefer Alembic (`alembic upgrade head`).
"""
from __future__ import annotations

import logging

from sqlalchemy import text

from app.db.models import Base
from app.db.session import sync_engine

logger = logging.getLogger(__name__)


def init_db() -> None:
    """
    1. Enable the pgvector extension.
    2. Create all tables defined in Base.metadata (if they don't exist).
    3. Create the HNSW index on the embedding column.
    """
    with sync_engine.begin() as conn:
        logger.info("Enabling pgvector extension...")
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))

        logger.info("Creating tables...")
        Base.metadata.create_all(bind=conn)

        # The HNSW index must be created after the table exists and uses
        # raw DDL because SQLAlchemy doesn't expose pgvector index options.
        logger.info("Creating HNSW index on reviews.embedding...")
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS ix_reviews_embedding_hnsw
                ON reviews
                USING hnsw (embedding vector_cosine_ops)
                WITH (m = 16, ef_construction = 64)
                """
            )
        )

    logger.info("Database initialised successfully.")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_db()
