"""
Celery tasks for async scraping and embedding ingestion.
Uses repository classes — no raw SQL in this file.
"""
from __future__ import annotations

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.db.models import ReviewSource
from app.db.repositories.review_repo import SyncReviewRepository
from app.db.repositories.scrape_job_repo import SyncScrapeJobRepository
from app.db.session import sync_engine
from app.services.cleaner import clean_reviews
from app.services.embedder import embed_texts
from app.services.scraper import scrape_source
from app.worker.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, name="tasks.run_scrape_job", max_retries=2)
def run_scrape_job(self, job_id: str, source: Optional[str] = None, count: int = 500):
    """
    Full ingestion pipeline:
      1. Scrape raw reviews.
      2. Clean + deduplicate.
      3. Bulk-upsert into PostgreSQL (skip existing hashes).
      4. Generate and store embeddings for new rows.
      5. Update the ScrapeJob status record.
    """
    with Session(sync_engine) as db:
        job_repo    = SyncScrapeJobRepository(db)
        review_repo = SyncReviewRepository(db)

        job = job_repo.get(job_id)
        if not job:
            logger.error("ScrapeJob %s not found in DB", job_id)
            return

        job_repo.mark_running(job, celery_task_id=self.request.id)

        try:
            # ── 1. Scrape ────────────────────────────────────────────
            raw_reviews = scrape_source(source, count)
            logger.info("[job %s] raw reviews fetched: %d", job_id, len(raw_reviews))

            # ── 2. Clean ─────────────────────────────────────────────
            cleaned = clean_reviews(raw_reviews)
            logger.info("[job %s] after cleaning: %d", job_id, len(cleaned))

            # ── 3. Upsert ────────────────────────────────────────────
            rows = [
                {
                    "source":          ReviewSource(r.source),
                    "author":          r.author,
                    "rating":          r.rating,
                    "content":         r.raw_content,
                    "cleaned_content": r.cleaned_content,
                    "review_date":     r.review_date,
                    "content_hash":    r.content_hash,
                    "external_id":     r.external_id,
                }
                for r in cleaned
            ]
            added = review_repo.bulk_upsert(rows)

            # ── 4. Embed reviews that have no vector yet ──────────────
            _embed_unprocessed(review_repo)

            # ── 5. Mark job complete ──────────────────────────────────
            job_repo.mark_completed(job, reviews_found=len(raw_reviews), reviews_added=added)
            logger.info("[job %s] completed — added %d reviews", job_id, added)

        except Exception as exc:
            logger.exception("[job %s] failed: %s", job_id, exc)
            job_repo.mark_failed(job, error=str(exc))
            raise self.retry(exc=exc, countdown=60)


def _embed_unprocessed(
    review_repo: SyncReviewRepository,
    batch_size: int = 200,
    max_per_run: int = 1000,
) -> None:
    """
    Fetch unembedded reviews and generate vectors in batches.
    Capped at max_per_run per job invocation to control API cost.
    """
    unembedded = review_repo.get_unembedded(limit=max_per_run)
    if not unembedded:
        return

    logger.info("Generating embeddings for %d reviews", len(unembedded))

    for i in range(0, len(unembedded), batch_size):
        batch  = unembedded[i : i + batch_size]
        texts  = [r.cleaned_content or r.content for r in batch]
        vectors = embed_texts(texts)
        review_repo.save_embeddings(list(zip(batch, vectors)))
        logger.info("Embedded reviews %d-%d", i + 1, i + len(batch))
