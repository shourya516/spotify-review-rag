"""
Dev entrypoint — runs without PostgreSQL, Redis, or OpenAI.

Uses:
  - SQLite  instead of PostgreSQL
  - In-process background tasks instead of Celery
  - Fake embeddings (random deterministic vectors)
  - Mock LLM that summarises retrieved reviews without calling OpenAI

Start with:
    python main_dev.py
"""
from __future__ import annotations

import hashlib
import json
import logging
import math
import os
import random
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import List, Literal, Optional

from dotenv import load_dotenv
load_dotenv(".env.dev", override=True)  # Load API keys from .env.dev

import uvicorn
from fastapi import BackgroundTasks, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import create_engine, func, select, desc, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import Session

# ── Bootstrap DB on startup ──────────────────────────────────────────
from app.db.init_dev import init_dev_db
from app.db.models_dev import Review, ScrapeJob, QueryLog

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

ASYNC_URL = "sqlite+aiosqlite:///./dev.db"
SYNC_URL  = "sqlite:///./dev.db"

async_engine = create_async_engine(ASYNC_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(async_engine, expire_on_commit=False)
sync_engine = create_engine(SYNC_URL, echo=False)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@asynccontextmanager
async def lifespan(app: FastAPI):
    load_dotenv(".env.dev", override=True)  # Re-load on subprocess start
    llm_key = os.getenv("LLM_API_KEY", "")
    logger.info("LLM_API_KEY loaded: %d chars, model=%s, base_url=%s",
                len(llm_key), os.getenv("LLM_MODEL", ""), os.getenv("LLM_BASE_URL", ""))
    init_dev_db()
    yield


app = FastAPI(
    title="Spotify Review RAG API (Dev)",
    description="Local dev mode — SQLite, fake embeddings, mock LLM.",
    version="0.1.0-dev",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Schemas ──────────────────────────────────────────────────────────

class ScrapeRequest(BaseModel):
    source: Optional[Literal["play_store", "app_store", "reddit"]] = None
    count: int = Field(default=500, ge=1, le=2000)


class ScrapeJobOut(BaseModel):
    id: str
    source: Optional[str]
    status: str
    reviews_found: int
    reviews_added: int
    error_message: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}


class ReviewOut(BaseModel):
    id: str
    source: str
    author: Optional[str]
    rating: Optional[int]
    cleaned_content: str
    review_date: Optional[datetime]
    scraped_at: datetime

    model_config = {"from_attributes": True}


class ReviewListResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: List[ReviewOut]


class ReviewStats(BaseModel):
    total: int
    by_source: dict
    missing_embeddings: int


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=1000)
    top_k: Optional[int] = Field(default=None, ge=1, le=50)
    min_similarity: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class CitationOut(BaseModel):
    review_id: str
    source: str
    author: Optional[str]
    rating: Optional[int]
    snippet: str
    similarity: float


class QueryResponse(BaseModel):
    question: str
    answer: str
    citations: List[CitationOut]
    latency_ms: Optional[int]


# ── Helpers ──────────────────────────────────────────────────────────

def _sha256(t: str) -> str:
    return hashlib.sha256(t.encode()).hexdigest()


def _fake_embedding(text: str) -> list[float]:
    rng = random.Random(hash(text) & 0xFFFFFFFF)
    return [round(rng.uniform(-1, 1), 6) for _ in range(1536)]


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot  = sum(x * y for x, y in zip(a, b))
    na   = math.sqrt(sum(x * x for x in a))
    nb   = math.sqrt(sum(x * x for x in b))
    return dot / (na * nb) if na and nb else 0.0


def _mock_llm_answer(question: str, reviews: list[dict]) -> str:
    """
    Uses LLM_API_KEY + LLM_BASE_URL (DeepSeek or any OpenAI-compatible API).
    Falls back to OPENAI_API_KEY if LLM vars aren't set.
    Falls back to mock if neither key is available.
    """
    # Priority: LLM_API_KEY (DeepSeek) > OPENAI_API_KEY > mock
    api_key = os.getenv("LLM_API_KEY", "").strip()
    base_url = os.getenv("LLM_BASE_URL", "").strip() or None
    model = os.getenv("LLM_MODEL", "deepseek-chat").strip()

    # Fall back to OpenAI if no LLM key
    if not api_key or api_key == "sk-your-deepseek-key-here":
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        base_url = None  # use default OpenAI URL
        model = os.getenv("OPENAI_LLM_MODEL", "gpt-4o-mini").strip()

    # Build context from reviews
    context_blocks = []
    for i, r in enumerate(reviews, 1):
        src = r["source"].replace("_", " ").title()
        rating_str = f" Rating: {r['rating']}/5" if r.get("rating") else ""
        context_blocks.append(
            f"[Review {i}] (Source: {src}{rating_str})\n{r['cleaned_content'][:600]}"
        )
    context = "\n\n".join(context_blocks)

    # ── Real LLM call (OpenAI-compatible: Grok, DeepSeek, OpenAI) ───
    if api_key and api_key not in ("", "sk-...", "sk-your-deepseek-key-here", "your-gemini-api-key-here", "your-xai-api-key-here", "your-openrouter-key-here", "your-groq-key-here"):
        try:
            from openai import OpenAI
            client_kwargs = {"api_key": api_key}
            if base_url:
                client_kwargs["base_url"] = base_url
            client = OpenAI(**client_kwargs)
            logger.info("Calling LLM: model=%s base_url=%s", model, base_url or "default")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a product analyst. Answer questions about Spotify "
                            "based ONLY on the user reviews provided. "
                            "Cite reviews by number [Review N]. "
                            "Be concise. Use bullet points."
                        ),
                    },
                    {
                        "role": "user",
                        "content": f"--- USER REVIEWS ---\n{context}\n--- END ---\n\nQuestion: {question}\n\nAnswer:",
                    },
                ],
                temperature=0.2,
                max_tokens=1024,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            logger.error("LLM call failed: %s — falling back to mock", exc)
            error_msg = str(exc)

    # ── Fallback mock ────────────────────────────────────────────
    # Show the actual error so user knows what went wrong
    error_info = ""
    if 'error_msg' in dir():
        error_info = f"\n\n⚠️ **LLM Error:** {error_msg}"
    
    lines = [
        f"**[Dev Mode — Mock Answer]**\n",
        f"Based on {len(reviews)} retrieved reviews for: *{question}*\n",
    ]
    for i, r in enumerate(reviews, 1):
        src = r["source"].replace("_", " ").title()
        rating = f" ★{r['rating']}/5" if r.get("rating") else ""
        lines.append(f"[Review {i}] ({src}{rating}): {r['cleaned_content'][:200]}…")
    
    if error_info:
        lines.append(error_info)
    else:
        lines.append(
            "\n_This is a mock answer. Add your LLM_API_KEY to .env.dev for AI-generated responses._"
        )
    return "\n\n".join(lines)


# ── Background scrape task (runs in-process, no Celery) ──────────────

# Template pools — combined with index suffixes to generate large unique sets

_PLAY_STORE_TEMPLATES = [
    (5, "Absolutely love Spotify. The music discovery is top notch and the app is buttery smooth."),
    (4, "Great app overall. Discover Weekly never misses and the UI is clean."),
    (4, "Spotify is my go-to music app. The curated playlists are excellent."),
    (3, "Decent app but the free tier has way too many ads between songs."),
    (3, "The shuffle feature feels rigged — it keeps playing the same 5 songs."),
    (2, "Battery drain has gotten noticeably worse after the latest update."),
    (2, "The app crashes every time I try to download songs for offline listening."),
    (1, "Forced me to shuffle on mobile as a free user. Extremely frustrating."),
    (1, "Ads every 30 seconds on the free tier makes the app unusable."),
    (5, "Spotify Connect works flawlessly across all my devices. Best feature."),
    (4, "Love the Daily Mix playlists. They always introduce me to new music I enjoy."),
    (3, "The home screen redesign is confusing. Hard to find recently played."),
    (2, "Keeps logging me out randomly and losing my queue."),
    (1, "Premium price went up but quality of recommendations went down."),
    (5, "The podcast integration is seamless. One app for everything audio."),
    (4, "Crossfade feature is great for parties. Wish the equalizer had more options."),
    (3, "Offline downloads work but the download manager UI is confusing."),
    (2, "Search results are cluttered with sponsored content now."),
    (5, "Best music streaming app on Android. Period. Fast, reliable, great library."),
    (4, "Social features like Blend are really fun with friends."),
    (3, "The algorithm is good but sometimes feels like it's stuck in a loop."),
    (2, "App freezes when switching between songs rapidly."),
    (1, "Lost all my playlists after an update. No backup option provided."),
    (4, "Lyrics feature is really useful, especially for learning song words."),
    (3, "Wish there was a way to block certain artists from recommendations."),
    (2, "The mini-player disappears randomly while browsing."),
    (5, "Collaborative playlists are a game changer for road trips with friends."),
    (1, "The app used to be great. Now it's bloated with features nobody asked for."),
    (4, "Queue management has improved a lot. Can finally see upcoming songs easily."),
    (3, "Student discount is good value but the verification process is annoying."),
]

_APP_STORE_TEMPLATES = [
    (5, "Spotify on iOS is incredibly smooth. Best music app in the App Store by far."),
    (4, "Really enjoy using Spotify daily. The music library is massive and well organized."),
    (4, "Discover Weekly is always on point. Introduced me to so many new artists."),
    (3, "Good app but it drains my iPhone battery faster than any other app."),
    (3, "The UI changes in the latest update made things harder to navigate."),
    (2, "Keeps buffering even on fast WiFi. Never had this issue before the update."),
    (2, "The sleep timer I requested years ago still isn't a built-in feature."),
    (1, "App crashes on launch after every major iOS update. Very frustrating."),
    (1, "Free users get a terrible experience. Constant ads and no song skipping."),
    (5, "Spotify Connect between my iPhone and HomePod is flawless. Love it."),
    (4, "The canvas video backgrounds for songs are a nice aesthetic touch."),
    (3, "Wish you could import local files more easily like the old version allowed."),
    (2, "Notifications for new releases from followed artists often come late."),
    (1, "Removed the ability to sort playlists by date added. Very annoying change."),
    (5, "Family plan is excellent value. Everyone in my house has their own account."),
    (4, "The Car Mode feature makes it safe and easy to use while driving."),
    (3, "Algorithm keeps recommending artists I've already heard. Needs refreshing."),
    (2, "Profile and social features feel unfinished and buggy."),
    (5, "Siri integration works great. Can ask to play anything hands-free."),
    (4, "The equalizer in premium is solid. Makes a big difference on good headphones."),
    (3, "The app takes too long to load on older iPhones."),
    (2, "Downloaded playlists sometimes disappear after phone restart."),
    (1, "Charged twice this month. Support took a week to respond."),
    (4, "Liked Songs playlist is massive and easy to manage. Love the filter feature."),
    (3, "Spotify Wrapped is fun but the rest of the year-end features feel thin."),
    (2, "The new home feed feels like Instagram. I just want to find music easily."),
    (5, "AirPlay support is rock solid. Never drops connection unlike some competitors."),
    (1, "Cancelled premium because price increased without any noticeable improvements."),
    (4, "Radio stations based on a song or artist are surprisingly accurate."),
    (3, "Would love a dark mode option that is even darker than the current theme."),
]

_REDDIT_TEMPLATES = [
    (None, "Spotify's recommendation algorithm has seriously degraded. My Release Radar is full of artists I listened to once six months ago."),
    (None, "Anyone else find that Spotify's Discover Weekly has gotten worse? It used to feel magical. Now it's just recycling my existing library."),
    (None, "The free tier on Spotify mobile is basically unusable now. An ad every two songs is predatory."),
    (None, "I switched from Apple Music back to Spotify just for the social features and collaborative playlists. Worth it."),
    (None, "Spotify's offline download limit of 10,000 songs is way too low for serious collectors."),
    (None, "The new home screen update is terrible UX. Why would you hide recently played behind a scroll?"),
    (None, "Spotify Connect is genuinely the best feature in music streaming. Switching devices mid-song seamlessly is magic."),
    (None, "Does anyone else feel like the audio quality on Spotify Free is noticeably worse than Premium? The compression is really obvious."),
    (None, "Just hit my 10,000 song download limit for offline. Spotify please increase this or let us manage it better."),
    (None, "The Blend feature with friends is underrated. We discovered three new mutual favorite artists through it."),
    (None, "Why does Spotify still not have a sleep timer built in? Third party apps shouldn't be necessary for this."),
    (None, "Spotify's podcast recommendations are completely separate from music recommendations. Feels like two different products bolted together."),
    (None, "The price increase wasn't justified. I'm paying more for the same library and worse recommendations than a year ago."),
    (None, "Spotify's queue system is finally usable after years of it being broken. Small win but appreciated."),
    (None, "I love that Spotify keeps all my listening history. Makes it easy to remember albums I discovered years ago."),
    (None, "The canvas animated backgrounds are cool in theory but they absolutely murder battery life."),
    (None, "Spotify's student discount is legitimately one of the best deals in subscription software right now."),
    (None, "Why can't Spotify let me block specific artists from ever appearing in my recommendations? This seems basic."),
    (None, "The Daily Mix playlists are still my favorite Spotify feature after all these years. Consistently excellent."),
    (None, "Spotify wrapped feels more like a marketing campaign than a genuine user feature these days."),
    (None, "Premium family plan is incredible value if you have 2+ people. Five accounts for less than two individual subscriptions."),
    (None, "The algorithm pushed a niche ambient artist to me last week that I've been listening to on repeat. When it works, it really works."),
    (None, "Spotify's 30-second preview before download on poor connections is a nice UX touch that more apps should copy."),
    (None, "I miss the old Spotify UI. Every update seems to make discovery harder and push promoted content more."),
    (None, "The in-app lyrics feature has made listening to music so much more enjoyable. Should have been added years ago."),
    (None, "Spotify's social feed is completely dead. Nobody I know uses the friend activity feature despite it being there for years."),
    (None, "The shuffle algorithm is demonstrably not random. It clearly weights recently added and frequently played songs."),
    (None, "Car Mode on iOS is genuinely good and safe to use while driving. Google Maps integration makes it even better."),
    (None, "I wish Spotify had better tools for managing very large playlists. Sorting and filtering options are too limited."),
    (None, "Spotify's crossfade feature at 3 seconds is the perfect setting for continuous listening. Highly recommend trying it."),
]


def _generate_mock_reviews(source: str, count: int) -> list[tuple]:
    """Generate `count` unique mock reviews for the given source by cycling templates with unique suffixes."""
    if source == "play_store":
        templates = _PLAY_STORE_TEMPLATES
        author_prefix = "play_user_"
    elif source == "app_store":
        templates = _APP_STORE_TEMPLATES
        author_prefix = "ios_user_"
    else:
        templates = _REDDIT_TEMPLATES
        author_prefix = "u/reddit_user_"

    results = []
    for i in range(count):
        rating, base_content = templates[i % len(templates)]
        # Make each review unique by appending a variation note
        suffix_idx = i // len(templates)
        content = base_content if suffix_idx == 0 else f"{base_content} (review #{i + 1})"
        results.append((source, f"{author_prefix}{i + 1}", rating, content))
    return results


def _run_scrape_sync(job_id: str, source: Optional[str], count: int):
    """
    Real scraping pipeline using google-play-scraper and app-store-scraper.
    Falls back to mock data if a scraper fails (e.g. network unavailable).
    """
    from google_play_scraper import reviews as gps_reviews, Sort
    import hashlib

    PLAY_STORE_APP_ID = "com.spotify.music"
    APP_STORE_APP_ID  = "324684580"

    with Session(sync_engine) as db:
        job = db.get(ScrapeJob, job_id)
        if not job:
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        db.commit()

        raw_rows: list[dict] = []

        try:
            sources = [source] if source else ["play_store", "app_store", "reddit"]

            # ── Google Play Store ────────────────────────────────────
            if "play_store" in sources:
                logger.info("Scraping Google Play Store (count=%d)...", count)
                fetched = []
                continuation_token = None
                while len(fetched) < count:
                    batch_size = min(200, count - len(fetched))
                    try:
                        batch, continuation_token = gps_reviews(
                            PLAY_STORE_APP_ID,
                            lang="en", country="us",
                            sort=Sort.NEWEST,
                            count=batch_size,
                            continuation_token=continuation_token,
                        )
                        for r in batch:
                            content = (r.get("content") or "").strip()
                            if not content:
                                continue
                            raw_rows.append({
                                "source":          "play_store",
                                "author":          r.get("userName"),
                                "rating":          r.get("score"),
                                "content":         content,
                                "cleaned_content": content,
                                "content_hash":    _sha256(content),
                                "external_id":     r.get("reviewId", ""),
                                "review_date":     r.get("at"),
                            })
                        fetched.extend(batch)
                        logger.info("Play Store: %d fetched so far", len(fetched))
                        if not continuation_token or not batch:
                            break
                    except Exception as exc:
                        logger.error("Play Store scrape error: %s", exc)
                        break

            # ── Apple App Store (direct iTunes RSS JSON API — fast) ────
            if "app_store" in sources:
                logger.info("Scraping App Store via iTunes RSS API (count=%d)...", count)
                import httpx

                # iTunes RSS endpoint returns up to 50 reviews per page per country.
                # Fetch from multiple countries in parallel for speed.
                APP_STORE_COUNTRIES = ["us", "gb", "au", "ca", "in", "de"]
                pages_per_country = max(1, (count // (len(APP_STORE_COUNTRIES) * 50)) + 1)

                def _fetch_itunes_country(country: str) -> list[dict]:
                    rows: list[dict] = []
                    for page in range(1, pages_per_country + 1):
                        url = f"https://itunes.apple.com/{country}/rss/customerreviews/id=324684580/page={page}/sortby=mostrecent/json"
                        try:
                            resp = httpx.get(url, timeout=15.0)
                            if resp.status_code != 200:
                                break
                            data = resp.json()
                            entries = data.get("feed", {}).get("entry", [])
                            if not entries:
                                break
                            for entry in entries:
                                # Skip the app metadata entry
                                if "im:rating" not in entry:
                                    continue
                                content = (entry.get("content", {}).get("label") or "").strip()
                                if not content or len(content) < 10:
                                    continue
                                author_name = entry.get("author", {}).get("name", {}).get("label")
                                rating = int(entry.get("im:rating", {}).get("label", "0"))
                                review_id = entry.get("id", {}).get("label", "")
                                rows.append({
                                    "source":          "app_store",
                                    "author":          author_name,
                                    "rating":          rating if rating > 0 else None,
                                    "content":         content,
                                    "cleaned_content": content,
                                    "content_hash":    _sha256(content),
                                    "external_id":     review_id,
                                    "review_date":     datetime.now(timezone.utc),
                                })
                        except Exception as exc:
                            logger.warning("iTunes RSS [%s] page %d error: %s", country, page, exc)
                            break
                    return rows

                from concurrent.futures import ThreadPoolExecutor, as_completed
                seen_hashes: set[str] = set()
                with ThreadPoolExecutor(max_workers=6) as pool:
                    futures = {pool.submit(_fetch_itunes_country, c): c for c in APP_STORE_COUNTRIES}
                    for future in as_completed(futures):
                        for row in future.result():
                            h = row["content_hash"]
                            if h not in seen_hashes:
                                seen_hashes.add(h)
                                raw_rows.append(row)
                logger.info("App Store (iTunes RSS): %d reviews fetched", len(seen_hashes))

            # ── Reddit (requires credentials — skip if not configured) ─
            if "reddit" in sources:
                reddit_id = os.getenv("REDDIT_CLIENT_ID", "")
                reddit_secret = os.getenv("REDDIT_CLIENT_SECRET", "")
                if reddit_id and reddit_secret:
                    import praw
                    logger.info("Scraping Reddit...")
                    try:
                        reddit = praw.Reddit(
                            client_id=reddit_id,
                            client_secret=reddit_secret,
                            user_agent=os.getenv("REDDIT_USER_AGENT", "SpotifyReviewScraper/1.0"),
                            read_only=True,
                        )
                        for sub_name in ["spotify", "SpotifyTheft", "SpotifyAnnoyances"]:
                            try:
                                for post in reddit.subreddit(sub_name).new(limit=count // 3):
                                    body = post.selftext.strip()
                                    text = f"{post.title}\n\n{body}" if body not in ("", "[removed]", "[deleted]") else post.title
                                    raw_rows.append({
                                        "source": "reddit", "author": str(post.author) if post.author else None,
                                        "rating": None, "content": text, "cleaned_content": text,
                                        "content_hash": _sha256(text), "external_id": f"post_{post.id}",
                                        "review_date": datetime.utcfromtimestamp(post.created_utc),
                                    })
                            except Exception as exc:
                                logger.error("Reddit r/%s error: %s", sub_name, exc)
                    except Exception as exc:
                        logger.error("Reddit init error: %s", exc)
                else:
                    logger.warning("Reddit credentials not set — skipping Reddit scrape")

            # ── Upsert into DB ───────────────────────────────────────
            added = 0
            for row in raw_rows:
                if not row.get("content_hash"):
                    continue
                exists = db.query(Review).filter_by(content_hash=row["content_hash"]).first()
                if not exists:
                    db.add(Review(
                        id=str(uuid.uuid4()),
                        source=row["source"],
                        author=row.get("author"),
                        rating=row.get("rating"),
                        content=row["content"],
                        cleaned_content=row["cleaned_content"],
                        content_hash=row["content_hash"],
                        external_id=row.get("external_id"),
                        review_date=row.get("review_date"),
                        embedding=json.dumps(_fake_embedding(row["cleaned_content"])),
                    ))
                    added += 1

            db.commit()
            job.status        = "completed"
            job.reviews_found = len(raw_rows)
            job.reviews_added = added
            job.completed_at  = datetime.now(timezone.utc)
            db.commit()
            logger.info("Scrape job %s done — found=%d added=%d", job_id, len(raw_rows), added)

        except Exception as exc:
            logger.exception("Scrape job %s failed: %s", job_id, exc)
            job.status        = "failed"
            job.error_message = str(exc)
            job.completed_at  = datetime.now(timezone.utc)
            db.commit()


# ── Routes ───────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "mode": "dev-sqlite"}


# Scrape
@app.post("/scrape", response_model=ScrapeJobOut, status_code=202)
async def trigger_scrape(body: ScrapeRequest, background_tasks: BackgroundTasks):
    with Session(sync_engine) as db:
        job = ScrapeJob(
            id=str(uuid.uuid4()),
            source=body.source,
            status="pending",
            reviews_found=0,
            reviews_added=0,
            created_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        job_id = job.id

    background_tasks.add_task(_run_scrape_sync, job_id, body.source, body.count)

    with Session(sync_engine) as db:
        return db.get(ScrapeJob, job_id)


@app.get("/scrape/{job_id}", response_model=ScrapeJobOut)
async def get_scrape_job(job_id: str):
    with Session(sync_engine) as db:
        job = db.get(ScrapeJob, job_id)
        if not job:
            raise HTTPException(404, "Job not found")
        return job


@app.get("/scrape", response_model=List[ScrapeJobOut])
async def list_scrape_jobs(limit: int = 10):
    with Session(sync_engine) as db:
        rows = db.query(ScrapeJob).order_by(ScrapeJob.created_at.desc()).limit(limit).all()
        return rows


# Reviews
@app.get("/reviews/stats", response_model=ReviewStats)
async def review_stats():
    with Session(sync_engine) as db:
        rows = db.query(Review.source, func.count(Review.id)).group_by(Review.source).all()
        by_source = {r[0]: r[1] for r in rows}
        total = sum(by_source.values())
        missing = db.query(Review).filter(Review.embedding.is_(None)).count()
        return ReviewStats(total=total, by_source=by_source, missing_embeddings=missing)


@app.get("/reviews", response_model=ReviewListResponse)
async def list_reviews(
    source: Optional[str] = Query(default=None),
    rating: Optional[int] = Query(default=None, ge=1, le=5),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
):
    with Session(sync_engine) as db:
        q = db.query(Review).order_by(Review.scraped_at.desc())
        if source:
            q = q.filter(Review.source == source)
        if rating is not None:
            q = q.filter(Review.rating == rating)
        total = q.count()
        items = q.offset((page - 1) * page_size).limit(page_size).all()
        return ReviewListResponse(
            total=total, page=page, page_size=page_size, items=items
        )


# ── Clear & Deduplicate endpoints ────────────────────────────────────

@app.delete("/reviews", status_code=200)
async def clear_all_reviews():
    """Delete all reviews from the database. Fresh start."""
    with Session(sync_engine) as db:
        count = db.query(Review).count()
        db.query(Review).delete()
        db.commit()
    logger.info("Cleared all %d reviews", count)
    return {"deleted": count, "message": f"Deleted {count} reviews"}


@app.post("/reviews/deduplicate", status_code=200)
async def deduplicate_reviews():
    """
    Remove duplicate reviews based on content_hash.
    Keeps the first (oldest) occurrence of each unique review.
    """
    with Session(sync_engine) as db:
        # Find duplicate content_hashes
        from sqlalchemy import func as sqla_func
        
        # Get all reviews grouped by content_hash, find duplicates
        all_reviews = db.query(Review).order_by(Review.scraped_at.asc()).all()
        
        seen_hashes: dict[str, str] = {}  # hash -> first review id
        duplicates_to_delete: list[str] = []
        
        for r in all_reviews:
            if r.content_hash in seen_hashes:
                duplicates_to_delete.append(r.id)
            else:
                seen_hashes[r.content_hash] = r.id
        
        # Also check near-duplicate content (same text, different hash — shouldn't happen but safety net)
        seen_content: dict[str, str] = {}
        for r in all_reviews:
            if r.id in duplicates_to_delete:
                continue
            normalized = (r.cleaned_content or r.content).strip().lower()
            if normalized in seen_content:
                duplicates_to_delete.append(r.id)
            else:
                seen_content[normalized] = r.id
        
        # Delete duplicates
        if duplicates_to_delete:
            db.query(Review).filter(Review.id.in_(duplicates_to_delete)).delete(synchronize_session=False)
            db.commit()
        
        remaining = db.query(Review).count()
    
    logger.info("Deduplication: removed %d duplicates, %d reviews remaining", len(duplicates_to_delete), remaining)
    return {
        "duplicates_removed": len(duplicates_to_delete),
        "reviews_remaining": remaining,
    }


# Query / RAG
@app.post("/query", response_model=QueryResponse)
async def query_reviews(body: QueryRequest):
    t0 = time.monotonic()
    top_k = body.top_k or int(os.getenv("RAG_TOP_K", "20"))

    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.metrics.pairwise import cosine_similarity as sklearn_cosine
    import numpy as np

    with Session(sync_engine) as db:
        all_reviews = db.query(Review).all()

    if not all_reviews:
        return QueryResponse(
            question=body.question,
            answer="No reviews found. Trigger a scrape first.",
            citations=[],
            latency_ms=0,
        )

    # Build TF-IDF matrix from all review texts
    texts = [r.cleaned_content or r.content for r in all_reviews]
    
    # Include the query as the last document so it shares the same vocabulary
    texts_with_query = texts + [body.question]
    
    vectorizer = TfidfVectorizer(
        max_features=10000,
        stop_words="english",
        ngram_range=(1, 2),  # unigrams + bigrams for better matching
        min_df=2,
    )
    tfidf_matrix = vectorizer.fit_transform(texts_with_query)
    
    # Query vector is the last row
    query_vec = tfidf_matrix[-1]
    review_vecs = tfidf_matrix[:-1]
    
    # Compute cosine similarity between query and all reviews
    similarities = sklearn_cosine(query_vec, review_vecs).flatten()
    
    # Get top-k indices sorted by similarity (descending)
    top_indices = np.argsort(similarities)[::-1][:top_k]
    
    top = [(float(similarities[i]), all_reviews[i]) for i in top_indices if similarities[i] > 0.01]

    if not top:
        return QueryResponse(
            question=body.question,
            answer="Could not find relevant reviews for your question. Try rephrasing.",
            citations=[],
            latency_ms=int((time.monotonic() - t0) * 1000),
        )

    review_dicts = [
        {
            "id":              r.id,
            "source":          r.source,
            "author":          r.author,
            "rating":          r.rating,
            "cleaned_content": r.cleaned_content or r.content,
        }
        for _, r in top
    ]

    answer = _mock_llm_answer(body.question, review_dicts)
    latency_ms = int((time.monotonic() - t0) * 1000)

    citations = [
        CitationOut(
            review_id=str(r.id),
            source=r.source,
            author=r.author,
            rating=r.rating,
            snippet=(r.cleaned_content or r.content)[:300],
            similarity=round(float(sim), 4),
        )
        for sim, r in top
    ]

    # Log query
    with Session(sync_engine) as db:
        db.add(QueryLog(
            id=str(uuid.uuid4()),
            question=body.question,
            answer=answer,
            cited_review_ids=json.dumps([c.review_id for c in citations]),
            top_k_used=top_k,
            latency_ms=latency_ms,
            created_at=datetime.now(timezone.utc),
        ))
        db.commit()

    return QueryResponse(
        question=body.question,
        answer=answer,
        citations=citations,
        latency_ms=latency_ms,
    )


if __name__ == "__main__":
    uvicorn.run("main_dev:app", host="0.0.0.0", port=8000, reload=True)
