"""
Repository for the ScrapeJob table.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.db.models import ScrapeJob, ScrapeJobStatus, ReviewSource

logger = logging.getLogger(__name__)


class AsyncScrapeJobRepository:
    """Async repo for FastAPI route handlers."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, source: Optional[ReviewSource] = None
    ) -> ScrapeJob:
        job = ScrapeJob(
            source=source,
            status=ScrapeJobStatus.PENDING,
            reviews_found=0,
            reviews_added=0,
        )
        self._session.add(job)
        await self._session.flush()   # assigns the UUID without full commit
        await self._session.commit()
        await self._session.refresh(job)
        return job

    async def get(self, job_id: UUID) -> Optional[ScrapeJob]:
        return await self._session.get(ScrapeJob, job_id)

    async def list_recent(self, limit: int = 20) -> list[ScrapeJob]:
        result = await self._session.execute(
            select(ScrapeJob).order_by(desc(ScrapeJob.created_at)).limit(limit)
        )
        return list(result.scalars().all())


class SyncScrapeJobRepository:
    """Sync repo for Celery workers."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, job_id: str) -> Optional[ScrapeJob]:
        return self._session.get(ScrapeJob, job_id)

    def mark_running(self, job: ScrapeJob, celery_task_id: str) -> None:
        job.status = ScrapeJobStatus.RUNNING
        job.celery_task_id = celery_task_id
        job.started_at = datetime.now(timezone.utc)
        self._session.commit()

    def mark_completed(
        self, job: ScrapeJob, reviews_found: int, reviews_added: int
    ) -> None:
        job.status = ScrapeJobStatus.COMPLETED
        job.reviews_found = reviews_found
        job.reviews_added = reviews_added
        job.completed_at = datetime.now(timezone.utc)
        self._session.commit()

    def mark_failed(self, job: ScrapeJob, error: str) -> None:
        job.status = ScrapeJobStatus.FAILED
        job.error_message = error
        job.completed_at = datetime.now(timezone.utc)
        self._session.commit()
