from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class ReviewOut(BaseModel):
    id: UUID
    source: str
    author: Optional[str]
    rating: Optional[int]
    cleaned_content: str
    review_date: Optional[datetime]
    scraped_at: datetime

    model_config = {"from_attributes": True}


class ReviewListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[ReviewOut]


class ReviewStats(BaseModel):
    total: int
    by_source: dict[str, int]
    missing_embeddings: int
