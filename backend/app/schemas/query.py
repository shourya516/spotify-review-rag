from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(
        ...,
        min_length=5,
        max_length=1000,
        description="Natural-language question about Spotify user feedback.",
    )
    top_k: Optional[int] = Field(
        default=None,
        ge=1,
        le=50,
        description="Override number of reviews to retrieve.",
    )
    min_similarity: Optional[float] = Field(
        default=None,
        ge=0.0,
        le=1.0,
        description="Override minimum cosine similarity threshold.",
    )


class CitationOut(BaseModel):
    review_id: str
    source: str
    author: Optional[str]
    rating: Optional[int]
    snippet: str
    similarity: float


class QueryResponse(BaseModel):
    question: str
    answer: str
    citations: list[CitationOut]
    latency_ms: Optional[int] = None
