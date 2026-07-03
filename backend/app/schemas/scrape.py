from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class ScrapeRequest(BaseModel):
    source: Optional[Literal["play_store", "app_store", "reddit"]] = Field(
        default=None,
        description="Source to scrape. Omit to scrape all sources.",
    )
    count: int = Field(
        default=500,
        ge=10,
        le=2000,
        description="Approximate number of reviews to fetch per source.",
    )


class ScrapeJobOut(BaseModel):
    id: UUID
    source: Optional[str]
    status: str
    reviews_found: int
    reviews_added: int
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}
