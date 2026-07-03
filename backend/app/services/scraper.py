"""
Scraping service — fetches raw reviews from Google Play Store,
Apple App Store, and Reddit.

Each scraper returns a list of RawReview dataclasses that are then
handed off to the cleaning service before DB insertion.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import praw
from google_play_scraper import reviews as gps_reviews, Sort
from app_store_scraper import AppStore

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# ── Spotify identifiers ──────────────────────────────────────────────
PLAY_STORE_APP_ID = "com.spotify.music"
APP_STORE_APP_ID = "324684580"         # Spotify's numeric App Store ID
APP_STORE_APP_NAME = "spotify"
APP_STORE_COUNTRY = "us"
REDDIT_SUBREDDITS = ["spotify", "SpotifyTheft", "SpotifyAnnoyances"]


@dataclass
class RawReview:
    source: str                        # "play_store" | "app_store" | "reddit"
    external_id: str
    author: Optional[str]
    rating: Optional[int]              # None for Reddit
    content: str
    review_date: Optional[datetime]


# ── Google Play Store ────────────────────────────────────────────────

def scrape_play_store(count: int = 500) -> list[RawReview]:
    """
    Fetches up to `count` reviews from the Google Play Store.
    Uses continuation tokens to page through results.
    """
    results: list[RawReview] = []
    continuation_token = None

    while len(results) < count:
        batch_size = min(200, count - len(results))
        try:
            batch, continuation_token = gps_reviews(
                PLAY_STORE_APP_ID,
                lang="en",
                country="us",
                sort=Sort.NEWEST,
                count=batch_size,
                continuation_token=continuation_token,
            )
        except Exception as exc:
            logger.error("Play Store scrape failed: %s", exc)
            break

        for r in batch:
            results.append(
                RawReview(
                    source="play_store",
                    external_id=r.get("reviewId", ""),
                    author=r.get("userName"),
                    rating=r.get("score"),
                    content=r.get("content", ""),
                    review_date=r.get("at"),
                )
            )

        logger.info("Play Store: fetched %d reviews so far", len(results))

        if not continuation_token:
            break

    return results


# ── Apple App Store ──────────────────────────────────────────────────

def scrape_app_store(count: int = 500) -> list[RawReview]:
    """
    Fetches up to `count` reviews from the Apple App Store (US).
    """
    results: list[RawReview] = []
    try:
        app = AppStore(
            country=APP_STORE_COUNTRY,
            app_name=APP_STORE_APP_NAME,
            app_id=APP_STORE_APP_ID,
        )
        app.review(how_many=count)
        raw = app.reviews
    except Exception as exc:
        logger.error("App Store scrape failed: %s", exc)
        return results

    for r in raw:
        results.append(
            RawReview(
                source="app_store",
                external_id=str(r.get("id", "")),
                author=r.get("userName"),
                rating=r.get("rating"),
                content=r.get("review", ""),
                review_date=r.get("date"),
            )
        )

    logger.info("App Store: fetched %d reviews", len(results))
    return results


# ── Reddit ───────────────────────────────────────────────────────────

def scrape_reddit(posts_per_sub: int = 100) -> list[RawReview]:
    """
    Fetches top posts and their comments from configured Spotify subreddits.
    Both posts and comments are stored as individual reviews (rating = None).
    """
    results: list[RawReview] = []

    reddit = praw.Reddit(
        client_id=settings.reddit_client_id,
        client_secret=settings.reddit_client_secret,
        user_agent=settings.reddit_user_agent,
        read_only=True,
    )

    for sub_name in REDDIT_SUBREDDITS:
        try:
            subreddit = reddit.subreddit(sub_name)
            posts = list(subreddit.new(limit=posts_per_sub))
        except Exception as exc:
            logger.error("Reddit scrape failed for r/%s: %s", sub_name, exc)
            continue

        for post in posts:
            # Include post body if it has text content
            if post.selftext and post.selftext.strip() not in ("[removed]", "[deleted]", ""):
                results.append(
                    RawReview(
                        source="reddit",
                        external_id=f"post_{post.id}",
                        author=str(post.author) if post.author else None,
                        rating=None,
                        content=f"{post.title}\n\n{post.selftext}",
                        review_date=datetime.utcfromtimestamp(post.created_utc),
                    )
                )
            else:
                # Title-only post
                results.append(
                    RawReview(
                        source="reddit",
                        external_id=f"post_{post.id}",
                        author=str(post.author) if post.author else None,
                        rating=None,
                        content=post.title,
                        review_date=datetime.utcfromtimestamp(post.created_utc),
                    )
                )

            # Flatten all comments
            try:
                post.comments.replace_more(limit=0)
                for comment in post.comments.list():
                    if comment.body in ("[removed]", "[deleted]", ""):
                        continue
                    results.append(
                        RawReview(
                            source="reddit",
                            external_id=f"comment_{comment.id}",
                            author=str(comment.author) if comment.author else None,
                            rating=None,
                            content=comment.body,
                            review_date=datetime.utcfromtimestamp(comment.created_utc),
                        )
                    )
            except Exception as exc:
                logger.warning("Failed to fetch comments for post %s: %s", post.id, exc)

        logger.info("Reddit r/%s: fetched %d items so far", sub_name, len(results))

    return results


# ── Unified entry point ──────────────────────────────────────────────

def scrape_source(source: str | None, count: int = 500) -> list[RawReview]:
    """
    Scrape one or all sources.

    Args:
        source: "play_store" | "app_store" | "reddit" | None (all)
        count:  approximate number of items to fetch per source
    """
    if source == "play_store":
        return scrape_play_store(count)
    elif source == "app_store":
        return scrape_app_store(count)
    elif source == "reddit":
        return scrape_reddit(posts_per_sub=count // len(REDDIT_SUBREDDITS) or 50)
    else:
        results: list[RawReview] = []
        results.extend(scrape_play_store(count))
        results.extend(scrape_app_store(count))
        results.extend(scrape_reddit(posts_per_sub=count // len(REDDIT_SUBREDDITS) or 50))
        return results
