"""
POST /query — RAG pipeline endpoint.

Runs the blocking RAG logic (OpenAI + SQLAlchemy sync) in a thread pool
executor so the async event loop is never blocked.
"""
from __future__ import annotations

import asyncio
import logging
from functools import partial

from fastapi import APIRouter, HTTPException
from sqlalchemy.orm import Session

from app.db.session import sync_engine
from app.schemas.query import CitationOut, QueryRequest, QueryResponse
from app.services.rag import answer_query

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/query", tags=["query"])


def _run_rag_sync(
    question: str,
    top_k: int | None,
    min_similarity: float | None,
) -> QueryResponse:
    with Session(sync_engine) as db:
        result = answer_query(
            query=question,
            db=db,
            top_k=top_k,
            min_similarity=min_similarity,
        )

    return QueryResponse(
        question=result.query,
        answer=result.answer,
        latency_ms=result.latency_ms,
        citations=[
            CitationOut(
                review_id=c.review_id,
                source=c.source,
                author=c.author,
                rating=c.rating,
                snippet=c.snippet,
                similarity=c.similarity,
            )
            for c in result.citations
        ],
    )


@router.post("", response_model=QueryResponse)
async def query_reviews(body: QueryRequest):
    """
    Accept a natural-language question and return an AI-generated answer
    grounded in retrieved Spotify user reviews, complete with citations.
    """
    loop = asyncio.get_running_loop()
    try:
        response = await loop.run_in_executor(
            None,
            partial(_run_rag_sync, body.question, body.top_k, body.min_similarity),
        )
    except Exception as exc:
        logger.exception("RAG pipeline error: %s", exc)
        raise HTTPException(status_code=500, detail="RAG pipeline failed. Check server logs.")

    return response
