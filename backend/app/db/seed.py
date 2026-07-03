"""
seed.py — Load a small set of sample reviews for local development.

Usage (from the backend/ directory):
    python -m app.db.seed

This inserts ~20 synthetic Spotify reviews (no real scraping required)
so you can test the Q&A interface immediately without API credentials.
"""
from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import Session

from app.db.models import Review, ReviewSource
from app.db.session import sync_engine

logger = logging.getLogger(__name__)

_SEED_REVIEWS = [
    # ── Play Store ───────────────────────────────────────────────────
    {
        "source": ReviewSource.PLAY_STORE,
        "author": "alice_music",
        "rating": 2,
        "content": "The app crashes every time I try to shuffle my liked songs playlist. "
                   "This started after the latest update.",
        "days_ago": 3,
    },
    {
        "source": ReviewSource.PLAY_STORE,
        "author": "bob_premium",
        "rating": 4,
        "content": "Overall a great music app but the recommendation algorithm feels stale. "
                   "I keep seeing the same songs on Discover Weekly.",
        "days_ago": 7,
    },
    {
        "source": ReviewSource.PLAY_STORE,
        "author": "carlos_free",
        "rating": 1,
        "content": "Too many ads for free users. I get an ad every two songs which makes "
                   "it impossible to enjoy music on the go.",
        "days_ago": 1,
    },
    {
        "source": ReviewSource.PLAY_STORE,
        "author": "diana_r",
        "rating": 5,
        "content": "Love the podcast integration. Being able to switch between music and "
                   "podcasts in one app is super convenient.",
        "days_ago": 10,
    },
    {
        "source": ReviewSource.PLAY_STORE,
        "author": "evan_dev",
        "rating": 3,
        "content": "The offline download feature works well but the UI for managing "
                   "downloads is confusing. Hard to find which songs are downloaded.",
        "days_ago": 5,
    },
    # ── App Store ────────────────────────────────────────────────────
    {
        "source": ReviewSource.APP_STORE,
        "author": "fiona_ios",
        "rating": 2,
        "content": "Since the last iOS update the app drains my battery extremely fast. "
                   "I lose about 20% battery per hour just listening to music.",
        "days_ago": 2,
    },
    {
        "source": ReviewSource.APP_STORE,
        "author": "george_k",
        "rating": 5,
        "content": "Spotify Connect is a game-changer. I switch between my phone, laptop "
                   "and smart speaker seamlessly. No other app does this as well.",
        "days_ago": 14,
    },
    {
        "source": ReviewSource.APP_STORE,
        "author": "hannah_m",
        "rating": 3,
        "content": "Would love a sleep timer feature. I often fall asleep to music and "
                   "wake up to my phone dead because Spotify kept playing all night.",
        "days_ago": 8,
    },
    {
        "source": ReviewSource.APP_STORE,
        "author": "ivan_p",
        "rating": 1,
        "content": "The new home screen redesign is terrible. I cannot find my recently "
                   "played playlists easily anymore. Please revert the UI.",
        "days_ago": 4,
    },
    {
        "source": ReviewSource.APP_STORE,
        "author": "julia_s",
        "rating": 4,
        "content": "The crossfade feature is excellent for parties. My only complaint is "
                   "that the equaliser has too few presets compared to competitors.",
        "days_ago": 11,
    },
    # ── Reddit ───────────────────────────────────────────────────────
    {
        "source": ReviewSource.REDDIT,
        "author": "u/music_nerd_99",
        "rating": None,
        "content": "Does anyone else feel like Spotify's recommendation engine has gotten "
                   "worse? My Release Radar is full of artists I've only listened to once.",
        "days_ago": 6,
    },
    {
        "source": ReviewSource.REDDIT,
        "author": "u/spotifyhater_2024",
        "rating": None,
        "content": "Just cancelled my premium subscription. The price increase combined "
                   "with the removal of lyrics for free users was the last straw.",
        "days_ago": 2,
    },
    {
        "source": ReviewSource.REDDIT,
        "author": "u/audiophile_dan",
        "rating": None,
        "content": "The audio quality on Spotify Free is noticeably compressed compared "
                   "to Apple Music or Tidal. Premium is better but still not lossless.",
        "days_ago": 9,
    },
    {
        "source": ReviewSource.REDDIT,
        "author": "u/playlist_queen",
        "rating": None,
        "content": "Collaborative playlists are my favourite feature. My friend group "
                   "uses them for road trips and it works flawlessly.",
        "days_ago": 15,
    },
    {
        "source": ReviewSource.REDDIT,
        "author": "u/dev_lurker",
        "rating": None,
        "content": "The Spotify API is pretty good for developers but rate limits are "
                   "frustrating when building apps that need real-time data.",
        "days_ago": 20,
    },
    {
        "source": ReviewSource.REDDIT,
        "author": "u/commuter_vibes",
        "rating": None,
        "content": "Offline mode is essential for my subway commute but I keep hitting "
                   "the 10,000 song limit on downloads. Please increase this Spotify!",
        "days_ago": 3,
    },
    {
        "source": ReviewSource.PLAY_STORE,
        "author": "kim_free_user",
        "rating": 2,
        "content": "Free users are treated like second-class citizens. No shuffle control, "
                   "constant ads, and now they removed the ability to pick songs on mobile.",
        "days_ago": 12,
    },
    {
        "source": ReviewSource.APP_STORE,
        "author": "lena_w",
        "rating": 5,
        "content": "The Daily Mix playlists are perfect. They mix my favourite artists with "
                   "new discoveries I actually enjoy. Best feature on the platform.",
        "days_ago": 7,
    },
    {
        "source": ReviewSource.REDDIT,
        "author": "u/bug_reporter_x",
        "rating": None,
        "content": "Bug report: when playing a song from search results and then going "
                   "back to the home screen, the queue gets reset. Very annoying.",
        "days_ago": 1,
    },
    {
        "source": ReviewSource.PLAY_STORE,
        "author": "marco_t",
        "rating": 3,
        "content": "Music discovery has really declined. I used to find great new artists "
                   "through Spotify but lately the algorithm just pushes mainstream pop.",
        "days_ago": 17,
    },
]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def seed_reviews() -> int:
    """
    Insert seed reviews, skipping any that already exist (idempotent).
    Returns the number of rows actually inserted.
    """
    now = datetime.now(timezone.utc)

    rows = []
    for r in _SEED_REVIEWS:
        cleaned = r["content"].strip()
        rows.append(
            {
                "id":              uuid.uuid4(),
                "source":          r["source"],
                "author":          r["author"],
                "rating":          r["rating"],
                "content":         r["content"],
                "cleaned_content": cleaned,
                "review_date":     now - timedelta(days=r["days_ago"]),
                "content_hash":    _sha256(cleaned),
                "external_id":     None,
                "embedding":       None,   # embeddings generated separately
            }
        )

    with Session(sync_engine) as db:
        stmt = (
            pg_insert(Review)
            .values(rows)
            .on_conflict_do_nothing(index_elements=["content_hash"])
            .returning(Review.id)
        )
        result = db.execute(stmt)
        db.commit()
        inserted = len(result.fetchall())

    logger.info("Seed complete: %d / %d rows inserted", inserted, len(rows))
    return inserted


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    seed_reviews()
