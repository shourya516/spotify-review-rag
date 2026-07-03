"""
GET /reviews — list stored reviews with pagination and filtering.
GET /reviews/stats — per-source counts and embedding coverage.
"""
from __future__ import annotations

from typing import Literal, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ReviewSource
from app.db.repositories.review_repo import AsyncReviewRepository
from app.db.session import get_db
from app.schemas.review import ReviewListResponse, ReviewOut, ReviewStats

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.get("/stats", response_model=ReviewStats)
async def review_stats(db: AsyncSession = Depends(get_db)):
    """
    Return per-source review counts and how many reviews are
    still missing embeddings (useful for monitoring ingestion health).
    """
    repo = AsyncReviewRepository(db)
    by_source = await repo.count_by_source()
    missing_embeddings = await repo.count_without_embedding()

    return ReviewStats(
        by_source=by_source,
        total=sum(by_source.values()),
        missing_embeddings=missing_embeddings,
    )


@router.get("", response_model=ReviewListResponse)
async def list_reviews(
    source: Optional[Literal["play_store", "app_store", "reddit"]] = Query(
        default=None, description="Filter by source"
    ),
    rating: Optional[int] = Query(default=None, ge=1, le=5),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """List reviews with optional source / rating filters and pagination."""
    repo = AsyncReviewRepository(db)
    source_enum = ReviewSource(source) if source else None
    total, items = await repo.list_reviews(
        source=source_enum,
        rating=rating,
        page=page,
        page_size=page_size,
    )

    return ReviewListResponse(
        total=total,
        page=page,
        page_size=page_size,
        items=[ReviewOut.model_validate(r) for r in items],
    )
