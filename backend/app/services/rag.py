"""
RAG (Retrieval-Augmented Generation) pipeline.

Steps:
  1. Embed the user query.
  2. Retrieve top-K most similar reviews via pgvector cosine search.
  3. Build a citation-grounded prompt.
  4. Call the LLM.
  5. Persist the query + answer to query_logs.
  6. Return structured answer + citations.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Optional

from openai import OpenAI
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.repositories.query_log_repo import SyncQueryLogRepository
from app.db.repositories.review_repo import SyncReviewRepository
from app.services.embedder import embed_query

logger = logging.getLogger(__name__)
settings = get_settings()


# ── Data structures ──────────────────────────────────────────────────

@dataclass
class Citation:
    review_id: str
    source: str
    author: Optional[str]
    rating: Optional[int]
    snippet: str          # first 300 chars of cleaned_content
    similarity: float


@dataclass
class RAGResponse:
    answer: str
    citations: list[Citation]
    query: str
    latency_ms: int


# ── Prompt construction ──────────────────────────────────────────────

def _build_prompt(query: str, reviews: list[dict]) -> str:
    context_blocks = []
    for i, r in enumerate(reviews, start=1):
        rating_line = f"Rating: {r['rating']}/5\n" if r["rating"] else ""
        context_blocks.append(
            f"[Review {i}] Source: {r['source']} | {rating_line}"
            f"{r['cleaned_content'][:800]}"
        )

    context = "\n\n".join(context_blocks)

    return f"""You are a product analyst assistant. Answer questions about Spotify \
based ONLY on the user reviews provided below.

Rules:
- Ground every claim in the provided reviews.
- Cite reviews by number in brackets, e.g. [Review 3].
- If the reviews do not contain enough information to answer, say so clearly.
- Do not make up information or draw on external knowledge.
- Be concise. Use bullet points where appropriate.

--- USER REVIEWS ---
{context}
--- END OF REVIEWS ---

Question: {query}

Answer:"""


# ── LLM call ────────────────────────────────────────────────────────

def _call_llm(prompt: str) -> str:
    client = OpenAI(api_key=settings.openai_api_key)
    response = client.chat.completions.create(
        model=settings.openai_llm_model,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful product analyst. "
                    "Answer questions about Spotify using only the provided user reviews."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=1024,
    )
    return response.choices[0].message.content.strip()


# ── Public entry point ───────────────────────────────────────────────

def answer_query(
    query: str,
    db: Session,
    top_k: Optional[int] = None,
    min_similarity: Optional[float] = None,
) -> RAGResponse:
    """
    Full RAG pipeline: embed → retrieve → generate → log → return.

    Args:
        query:          Natural-language question.
        db:             Synchronous SQLAlchemy session.
        top_k:          Override number of reviews to retrieve.
        min_similarity: Override cosine similarity threshold.
    """
    t_start = time.monotonic()
    logger.info("RAG query: %s", query[:120])

    k = top_k or settings.rag_top_k
    min_sim = min_similarity or settings.rag_min_similarity

    # 1. Embed the query
    query_vector = embed_query(query)

    # 2. Retrieve relevant reviews via repository
    review_repo = SyncReviewRepository(db)
    raw_reviews = review_repo.similarity_search(
        query_vector=query_vector,
        top_k=k,
        min_similarity=min_sim,
    )

    if not raw_reviews:
        return RAGResponse(
            answer=(
                "I couldn't find any relevant reviews for your question. "
                "Try rephrasing, or trigger a new scrape to ingest more data."
            ),
            citations=[],
            query=query,
            latency_ms=int((time.monotonic() - t_start) * 1000),
        )

    # 3. Build prompt and call LLM
    prompt = _build_prompt(query, raw_reviews)
    answer_text = _call_llm(prompt)

    latency_ms = int((time.monotonic() - t_start) * 1000)

    # 4. Build citation objects
    citations = [
        Citation(
            review_id=str(r["id"]),
            source=r["source"],
            author=r.get("author"),
            rating=r.get("rating"),
            snippet=r["cleaned_content"][:300],
            similarity=round(float(r["similarity"]), 4),
        )
        for r in raw_reviews
    ]

    # 5. Persist to query_logs (best-effort — don't fail the response if this errors)
    try:
        log_repo = SyncQueryLogRepository(db)
        log_repo.create(
            question=query,
            answer=answer_text,
            cited_review_ids=[
                {"review_id": c.review_id, "similarity": c.similarity}
                for c in citations
            ],
            top_k_used=k,
            min_similarity=min_sim,
            latency_ms=latency_ms,
        )
    except Exception as log_exc:
        logger.warning("Failed to write query log: %s", log_exc)

    return RAGResponse(
        answer=answer_text,
        citations=citations,
        query=query,
        latency_ms=latency_ms,
    )
