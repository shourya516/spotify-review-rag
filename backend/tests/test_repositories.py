"""
Integration tests for the data layer repositories.
Requires a live PostgreSQL + pgvector instance (see conftest.py).
"""
from __future__ import annotations

import hashlib
import uuid

import pytest

from app.db.models import Review, ReviewSource, ScrapeJob, ScrapeJobStatus
from app.db.repositories.review_repo import SyncReviewRepository
from app.db.repositories.scrape_job_repo import SyncScrapeJobRepository
from app.db.repositories.query_log_repo import SyncQueryLogRepository


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


# ── Helpers ──────────────────────────────────────────────────────────

def _make_review_row(content: str, source: ReviewSource = ReviewSource.PLAY_STORE) -> dict:
    cleaned = content.strip()
    return {
        "id":              uuid.uuid4(),
        "source":          source,
        "author":          "test_user",
        "rating":          4,
        "content":         content,
        "cleaned_content": cleaned,
        "review_date":     None,
        "content_hash":    _sha256(cleaned),
        "external_id":     None,
        "embedding":       None,
    }


# ── Review repository ────────────────────────────────────────────────

class TestSyncReviewRepository:
    def test_bulk_upsert_inserts_new_rows(self, db_session):
        repo = SyncReviewRepository(db_session)
        rows = [
            _make_review_row("This is a great music app with smooth playback."),
            _make_review_row("The recommendation engine is really accurate for me."),
        ]
        inserted = repo.bulk_upsert(rows)
        assert inserted == 2

    def test_bulk_upsert_skips_duplicates(self, db_session):
        repo = SyncReviewRepository(db_session)
        row = _make_review_row("Duplicate review text here for testing purposes.")
        repo.bulk_upsert([row])
        # Insert the same row again — should be skipped
        inserted_again = repo.bulk_upsert([row])
        assert inserted_again == 0

    def test_get_unembedded_returns_rows_without_vectors(self, db_session):
        repo = SyncReviewRepository(db_session)
        row = _make_review_row("This review has no embedding yet.")
        repo.bulk_upsert([row])

        unembedded = repo.get_unembedded(limit=10)
        assert any(r.content_hash == row["content_hash"] for r in unembedded)

    def test_save_embeddings_persists_vector(self, db_session):
        repo = SyncReviewRepository(db_session)
        row = _make_review_row("Review to be embedded with a fake vector.")
        repo.bulk_upsert([row])

        unembedded = repo.get_unembedded(limit=1)
        assert unembedded, "Expected at least one unembedded review"

        # Fake 1536-dim vector
        fake_vector = [0.01] * 1536
        repo.save_embeddings([(unembedded[0], fake_vector)])

        # Re-fetch and verify
        updated = db_session.get(Review, unembedded[0].id)
        assert updated.embedding is not None


# ── ScrapeJob repository ─────────────────────────────────────────────

class TestSyncScrapeJobRepository:
    def _create_job(self, db_session) -> ScrapeJob:
        job = ScrapeJob(
            source=ReviewSource.PLAY_STORE,
            status=ScrapeJobStatus.PENDING,
            reviews_found=0,
            reviews_added=0,
        )
        db_session.add(job)
        db_session.commit()
        db_session.refresh(job)
        return job

    def test_mark_running(self, db_session):
        repo = SyncScrapeJobRepository(db_session)
        job  = self._create_job(db_session)
        repo.mark_running(job, celery_task_id="celery-abc-123")

        assert job.status == ScrapeJobStatus.RUNNING
        assert job.celery_task_id == "celery-abc-123"
        assert job.started_at is not None

    def test_mark_completed(self, db_session):
        repo = SyncScrapeJobRepository(db_session)
        job  = self._create_job(db_session)
        repo.mark_running(job, "celery-xyz")
        repo.mark_completed(job, reviews_found=100, reviews_added=80)

        assert job.status == ScrapeJobStatus.COMPLETED
        assert job.reviews_found == 100
        assert job.reviews_added == 80
        assert job.completed_at is not None

    def test_mark_failed(self, db_session):
        repo = SyncScrapeJobRepository(db_session)
        job  = self._create_job(db_session)
        repo.mark_failed(job, error="Connection timeout")

        assert job.status == ScrapeJobStatus.FAILED
        assert "timeout" in job.error_message


# ── QueryLog repository ──────────────────────────────────────────────

class TestSyncQueryLogRepository:
    def test_create_logs_query(self, db_session):
        repo = SyncQueryLogRepository(db_session)
        log = repo.create(
            question="What do users complain about most?",
            answer="Users mostly complain about ads and recommendations.",
            cited_review_ids=[{"review_id": str(uuid.uuid4()), "similarity": 0.92}],
            top_k_used=10,
            min_similarity=0.70,
            latency_ms=540,
        )
        assert log.id is not None
        assert "ads" in log.answer
        assert log.latency_ms == 540
