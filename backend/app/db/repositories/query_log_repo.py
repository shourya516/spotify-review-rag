"""
Repository for the QueryLog table.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import QueryLog

logger = logging.getLogger(__name__)


class SyncQueryLogRepository:
    """
    Synchronous repository used inside the RAG pipeline (Celery / thread executor).
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        question: str,
        answer: str,
        cited_review_ids: list[dict],
        top_k_used: Optional[int] = None,
        min_similarity: Optional[float] = None,
        latency_ms: Optional[int] = None,
    ) -> QueryLog:
        """
        Persist one RAG query result.

        cited_review_ids should be a list of dicts like:
            [{"review_id": "...", "similarity": 0.91}, ...]
        """
        log = QueryLog(
            question=question,
            answer=answer,
            cited_review_ids=json.dumps(cited_review_ids),
            top_k_used=top_k_used,
            min_similarity=min_similarity,
            latency_ms=latency_ms,
        )
        self._session.add(log)
        self._session.commit()
        self._session.refresh(log)
        logger.debug("Logged RAG query id=%s", log.id)
        return log
