"""
ORM models for the Spotify Review RAG system.

Tables
------
reviews      — cleaned review text + pgvector embedding
scrape_jobs  — tracks async scraping task status
query_logs   — records every RAG query + answer (analytics)
"""
from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Integer, Text, DateTime,
    Enum, UniqueConstraint, func, Index, Float, ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, relationship
from pgvector.sqlalchemy import Vector


class Base(DeclarativeBase):
    pass


# ── Enums ────────────────────────────────────────────────────────────

class ReviewSource(str, PyEnum):
    PLAY_STORE = "play_store"
    APP_STORE  = "app_store"
    REDDIT     = "reddit"


class ScrapeJobStatus(str, PyEnum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


# ── Tables ───────────────────────────────────────────────────────────

class Review(Base):
    """
    One row per unique review / Reddit comment.
    Deduplication is enforced via the content_hash unique constraint.
    The embedding column stores a 1536-dim vector produced by
    OpenAI text-embedding-3-small; used for cosine similarity search.
    """
    __tablename__ = "reviews"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source          = Column(Enum(ReviewSource, name="reviewsource"), nullable=False, index=True)
    author          = Column(String(255), nullable=True)
    rating          = Column(Integer, nullable=True)           # null for Reddit
    content         = Column(Text, nullable=False)             # raw scraped text
    cleaned_content = Column(Text, nullable=True)              # after cleaning pipeline
    review_date     = Column(DateTime(timezone=True), nullable=True)
    scraped_at      = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    content_hash    = Column(String(64), nullable=False)       # SHA-256 of cleaned_content
    external_id     = Column(String(255), nullable=True)       # platform-native ID

    # pgvector — 1536 dims matches text-embedding-3-small
    embedding       = Column(Vector(1536), nullable=True)

    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_reviews_content_hash"),
        Index("ix_reviews_source_date", "source", "review_date"),
        # The HNSW index is created by the Alembic migration (not here)
        # because SQLAlchemy doesn't support pgvector index DDL natively.
    )

    def __repr__(self) -> str:
        return f"<Review id={self.id} source={self.source} rating={self.rating}>"


class ScrapeJob(Base):
    """
    Tracks one async scraping run (one Celery task).
    Frontend polls this to show ingestion progress.
    """
    __tablename__ = "scrape_jobs"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    celery_task_id  = Column(String(255), nullable=True, unique=True)
    source          = Column(
        Enum(ReviewSource, name="reviewsource"), nullable=True
    )  # null = all sources
    status          = Column(
        Enum(ScrapeJobStatus, name="scrapejobstatus"),
        nullable=False,
        default=ScrapeJobStatus.PENDING,
    )
    reviews_found   = Column(Integer, nullable=False, default=0)
    reviews_added   = Column(Integer, nullable=False, default=0)
    error_message   = Column(Text, nullable=True)
    started_at      = Column(DateTime(timezone=True), nullable=True)
    completed_at    = Column(DateTime(timezone=True), nullable=True)
    created_at      = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<ScrapeJob id={self.id} source={self.source} status={self.status}>"


class QueryLog(Base):
    """
    Persists every RAG query together with the answer and the IDs of the
    reviews that were cited.  Useful for analytics and quality monitoring.
    """
    __tablename__ = "query_logs"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    question        = Column(Text, nullable=False)
    answer          = Column(Text, nullable=False)
    # JSON array of {review_id, similarity} objects stored as text
    cited_review_ids = Column(Text, nullable=True)
    top_k_used      = Column(Integer, nullable=True)
    min_similarity  = Column(Float, nullable=True)
    latency_ms      = Column(Integer, nullable=True)   # end-to-end wall time
    created_at      = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    def __repr__(self) -> str:
        return f"<QueryLog id={self.id} question={self.question[:40]!r}>"
