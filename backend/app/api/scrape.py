"""
/scrape endpoints

POST /scrape        — enqueue a scraping job
GET  /scrape/{id}   — poll job status
GET  /scrape        — list recent jobs
"""
from __future__ import annotations

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ReviewSource
from app.db.repositories.scrape_job_repo import AsyncScrapeJobRepository
from app.db.session import get_db
from app.schemas.scrape import ScrapeJobOut, ScrapeRequest
from app.worker.tasks import run_scrape_job

router = APIRouter(prefix="/scrape", tags=["scrape"])


@router.post("", response_model=ScrapeJobOut, status_code=202)
async def trigger_scrape(
    body: ScrapeRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Enqueue a review scraping job.
    Returns immediately with a job record; poll GET /scrape/{id} for status.
    """
    repo = AsyncScrapeJobRepository(db)
    source = ReviewSource(body.source) if body.source else None
    job = await repo.create(source=source)

    # Hand off to Celery — non-blocking from the API perspective
    run_scrape_job.delay(job_id=str(job.id), source=body.source, count=body.count)

    return job


@router.get("/{job_id}", response_model=ScrapeJobOut)
async def get_scrape_job(
    job_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """Return current status of a scraping job."""
    repo = AsyncScrapeJobRepository(db)
    job = await repo.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("", response_model=List[ScrapeJobOut])
async def list_scrape_jobs(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """Return the most recent scraping jobs."""
    repo = AsyncScrapeJobRepository(db)
    return await repo.list_recent(limit=limit)
