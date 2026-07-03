"""
Bootstrap the SQLite dev database and seed it with sample reviews.
Run once before starting the dev server:
    python -m app.db.init_dev
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import uuid
from datetime import datetime, timezone, timedelta

from sqlalchemy import create_engine, insert, text
from sqlalchemy.orm import Session

from app.db.models_dev import Base, Review, QueryLog, ScrapeJob

logger = logging.getLogger(__name__)

SYNC_URL = "sqlite:///./dev.db"

SEED_REVIEWS = [
    ("play_store", "alice_music",      2, "The app crashes every time I try to shuffle my liked songs playlist. This started after the latest update."),
    ("play_store", "bob_premium",      4, "Overall a great music app but the recommendation algorithm feels stale. I keep seeing the same songs on Discover Weekly."),
    ("play_store", "carlos_free",      1, "Too many ads for free users. I get an ad every two songs which makes it impossible to enjoy music on the go."),
    ("play_store", "diana_r",          5, "Love the podcast integration. Being able to switch between music and podcasts in one app is super convenient."),
    ("play_store", "evan_dev",         3, "The offline download feature works well but the UI for managing downloads is confusing. Hard to find which songs are downloaded."),
    ("play_store", "marco_t",          3, "Music discovery has really declined. I used to find great new artists through Spotify but lately the algorithm just pushes mainstream pop."),
    ("play_store", "kim_free_user",    2, "Free users are treated like second-class citizens. No shuffle control, constant ads, and now they removed the ability to pick songs on mobile."),
    ("app_store",  "fiona_ios",        2, "Since the last iOS update the app drains my battery extremely fast. I lose about 20% battery per hour just listening to music."),
    ("app_store",  "george_k",         5, "Spotify Connect is a game-changer. I switch between my phone, laptop and smart speaker seamlessly. No other app does this as well."),
    ("app_store",  "hannah_m",         3, "Would love a sleep timer feature. I often fall asleep to music and wake up to my phone dead because Spotify kept playing all night."),
    ("app_store",  "ivan_p",           1, "The new home screen redesign is terrible. I cannot find my recently played playlists easily anymore. Please revert the UI."),
    ("app_store",  "julia_s",          4, "The crossfade feature is excellent for parties. My only complaint is that the equaliser has too few presets compared to competitors."),
    ("app_store",  "lena_w",           5, "The Daily Mix playlists are perfect. They mix my favourite artists with new discoveries I actually enjoy. Best feature on the platform."),
    ("reddit",     "u/music_nerd_99",  None, "Does anyone else feel like Spotify's recommendation engine has gotten worse? My Release Radar is full of artists I've only listened to once."),
    ("reddit",     "u/spotifyhater",   None, "Just cancelled my premium subscription. The price increase combined with the removal of lyrics for free users was the last straw."),
    ("reddit",     "u/audiophile_dan", None, "The audio quality on Spotify Free is noticeably compressed. Premium is better but still not lossless like Apple Music or Tidal."),
    ("reddit",     "u/playlist_queen", None, "Collaborative playlists are my favourite feature. My friend group uses them for road trips and it works flawlessly."),
    ("reddit",     "u/commuter_vibes", None, "Offline mode is essential for my subway commute but I keep hitting the 10,000 song limit on downloads. Please increase this Spotify!"),
    ("reddit",     "u/bug_reporter_x", None, "Bug report: when playing a song from search results and then going back to the home screen, the queue gets reset. Very annoying."),
    ("reddit",     "u/dev_lurker",     None, "The Spotify API is pretty good for developers but rate limits are frustrating when building apps that need real-time data."),
]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def _fake_embedding(text: str) -> str:
    """Generate a deterministic fake 1536-dim embedding as JSON (for dev only)."""
    rng = random.Random(hash(text) & 0xFFFFFFFF)
    vec = [round(rng.uniform(-1, 1), 6) for _ in range(1536)]
    return json.dumps(vec)


def init_dev_db() -> None:
    engine = create_engine(SYNC_URL, echo=False)
    Base.metadata.create_all(engine)
    logger.info("Tables created.")

    now = datetime.now(timezone.utc)
    with Session(engine) as db:
        existing = db.query(Review).count()
        if existing > 0:
            logger.info("DB already seeded (%d reviews). Skipping.", existing)
            return

        rows = []
        for i, (source, author, rating, content) in enumerate(SEED_REVIEWS):
            cleaned = content.strip()
            rows.append(Review(
                id=str(uuid.uuid4()),
                source=source,
                author=author,
                rating=rating,
                content=content,
                cleaned_content=cleaned,
                content_hash=_sha256(cleaned),
                review_date=now - timedelta(days=i + 1),
                external_id=None,
                embedding=_fake_embedding(cleaned),
            ))

        db.add_all(rows)
        db.commit()
        logger.info("Seeded %d reviews with fake embeddings.", len(rows))


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    init_dev_db()
