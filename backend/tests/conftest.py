"""
Pytest fixtures for data-layer integration tests.

Requires a running PostgreSQL instance with pgvector installed.
Set TEST_DATABASE_URL in your environment or .env.test to override.

Example:
    TEST_DATABASE_URL=postgresql+psycopg2://postgres:password@localhost:5432/spotify_reviews_test
"""
from __future__ import annotations

import os

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from app.db.models import Base


TEST_DB_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql+psycopg2://postgres:password@localhost:5432/spotify_reviews_test",
)


@pytest.fixture(scope="session")
def test_engine():
    """
    Create a dedicated test engine and initialise the schema once per
    test session.  Drops and recreates all tables so every run starts clean.
    """
    engine = create_engine(TEST_DB_URL, echo=False)

    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        # Drop all then recreate for a fresh slate
        Base.metadata.drop_all(bind=conn)
        Base.metadata.create_all(bind=conn)
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

    yield engine
    engine.dispose()


@pytest.fixture
def db_session(test_engine):
    """
    Yield a transactional session that is rolled back after every test,
    keeping the DB clean between tests without truncating tables.
    """
    connection = test_engine.connect()
    transaction = connection.begin()
    session = Session(bind=connection)

    yield session

    session.close()
    transaction.rollback()
    connection.close()
