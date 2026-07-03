"""
SQLite-compatible ORM models for local development.
Replaces the pgvector Vector column with a plain Text column (JSON string).
Import this instead of models.py when running in dev mode.
"""
from __future__ import annotations

import uuid
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, String, Integer, Text, DateTime,
    Enum, UniqueConstraint, func, Index, Float,
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.orm import DeclarativeBase


# SQLite-safe UUID type
class UUID(TypeDecorator):
    impl = CHAR(36)
    cache_ok = True

    def process_bind_param(self, value, dialect):
        return str(value) if value else None

    def process_result_value(self, value, dialect):
        return value


class Base(DeclarativeBase):
    pass


class ReviewSource(str, PyEnum):
    PLAY_STORE = "play_store"
    APP_STORE  = "app_store"
    REDDIT     = "reddit"


class ScrapeJobStatus(str, PyEnum):
    PENDING   = "pending"
    RUNNING   = "running"
    COMPLETED = "completed"
    FAILED    = "failed"


class Review(Base):
    __tablename__ = "reviews"

    id              = Column(UUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    source          = Column(String(20), nullable=False, index=True)
    author          = Column(String(255), nullable=True)
    rating          = Column(Integer, nullable=True)
    content         = Column(Text, nullable=False)
    cleaned_content = Column(Text, nullable=True)
    review_date     = Column(DateTime, nullable=True)
    scraped_at      = Column(DateTime, server_default=func.now(), nullable=False)
    content_hash    = Column(String(64), nullable=False)
    external_id     = Column(String(255), nullable=True)
    # In dev mode, store embedding as JSON text (no pgvector needed)
    embedding       = Column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("content_hash", name="uq_reviews_content_hash"),
    )


class ScrapeJob(Base):
    __tablename__ = "scrape_jobs"

    id              = Column(UUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    celery_task_id  = Column(String(255), nullable=True, unique=True)
    source          = Column(String(20), nullable=True)
    status          = Column(String(20), nullable=False, default="pending")
    reviews_found   = Column(Integer, nullable=False, default=0)
    reviews_added   = Column(Integer, nullable=False, default=0)
    error_message   = Column(Text, nullable=True)
    started_at      = Column(DateTime, nullable=True)
    completed_at    = Column(DateTime, nullable=True)
    created_at      = Column(DateTime, server_default=func.now(), nullable=False)


class QueryLog(Base):
    __tablename__ = "query_logs"

    id               = Column(UUID(), primary_key=True, default=lambda: str(uuid.uuid4()))
    question         = Column(Text, nullable=False)
    answer           = Column(Text, nullable=False)
    cited_review_ids = Column(Text, nullable=True)
    top_k_used       = Column(Integer, nullable=True)
    min_similarity   = Column(Float, nullable=True)
    latency_ms       = Column(Integer, nullable=True)
    created_at       = Column(DateTime, server_default=func.now(), nullable=False)
