"""
Repository for the Review table.

AsyncReviewRepository  — used by FastAPI route handlers
SyncReviewRepository   — used by Celery tasks (blocking I/O is fine in workers)
"""
from __future__ import annotations

import json
import logging
from typing import Optional
from uuid import UUID

from sqlalchemy import func, select, text, desc
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.db.models import Review, ReviewSource

logger = logging.getLogger(__name__)


# ── Async repository (FastAPI) ───────────────────────────────────────

class AsyncReviewRepository:
    """All database access for the reviews table in async context."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, review_id: UUID) -> Optional[Review]:
        return await self._session.get(Review, review_id)

    async def list_reviews(
        self,
        source: Optional[ReviewSource] = None,
        rating: Optional[int] = None,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[int, list[Review]]:
        """
        Return (total_count, page_of_reviews).
        Ordered by scraped_at descending (newest first).
        """
        query = select(Review).order_by(desc(Review.scraped_at))

        if source is not None:
            query = query.where(Review.source == source)
        if rating is not None:
            query = query.where(Review.rating == rating)

        # Total count
        count_result = await self._session.execute(
            select(func.count()).select_from(query.subquery())
        )
        total = count_result.scalar_one()

        # Paginated slice
        offset = (page - 1) * page_size
        result = await self._session.execute(query.offset(offset).limit(page_size))
        reviews = list(result.scalars().all())

        return total, reviews

    async def count_by_source(self) -> dict[str, int]:
        """Return {source: count} for all sources."""
        result = await self._session.execute(
            select(Review.source, func.count(Review.id))
            .group_by(Review.source)
        )
        return {row[0]: row[1] for row in result.fetchall()}

    async def count_without_embedding(self) -> int:
        result = await self._session.execute(
            select(func.count(Review.id)).where(Review.embedding.is_(None))
        )
        return result.scalar_one()


# ── Sync repository (Celery workers) ────────────────────────────────

class SyncReviewRepository:
    """All database access for the reviews table in synchronous context."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, rows: list[dict]) -> int:
        """
        Insert reviews, silently skipping rows that violate the
        content_hash unique constraint (i.e. already exist).

        Returns the number of rows actually inserted.
        """
        if not rows:
            return 0

        stmt = (
            pg_insert(Review)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["content_hash"])
            .returning(Review.id)
        )
        result = self._session.execute(stmt)
        self._session.commit()
        inserted = len(result.fetchall())
        logger.info("bulk_upsert: inserted %d / %d rows", inserted, len(rows))
        return inserted

    def get_unembedded(self, limit: int = 500) -> list[Review]:
        """Return reviews that still have no embedding vector."""
        return (
            self._session.query(Review)
            .filter(Review.embedding.is_(None))
            .limit(limit)
            .all()
        )

    def save_embeddings(self, review_vector_pairs: list[tuple[Review, list[float]]]) -> None:
        """Persist embedding vectors for a batch of Review objects."""
        for review, vector in review_vector_pairs:
            review.embedding = vector
        self._session.commit()

    def similarity_search(
        self,
        query_vector: list[float],
        top_k: int = 10,
        min_similarity: float = 0.70,
    ) -> list[dict]:
        """
        Cosine similarity search via pgvector's <=> operator.
        Returns a list of dicts ordered by descending similarity.
        """
        sql = text(
            """
            SELECT
                id,
                source,
                author,
                rating,
                cleaned_content,
                review_date,
                1 - (embedding <=> CAST(:embedding AS vector)) AS similarity
            FROM reviews
            WHERE
                embedding IS NOT NULL
                AND 1 - (embedding <=> CAST(:embedding AS vector)) >= :min_sim
            ORDER BY embedding <=> CAST(:embedding AS vector)
            LIMIT :top_k
            """
        )
        rows = self._session.execute(
            sql,
            {
                "embedding": str(query_vector),
                "min_sim": min_similarity,
                "top_k": top_k,
            },
        ).fetchall()
        return [row._asdict() for row in rows]
