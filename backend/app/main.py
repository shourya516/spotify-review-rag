"""
FastAPI application entry point.
"""
from __future__ import annotations

import logging

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.query import router as query_router
from app.api.reviews import router as reviews_router
from app.api.scrape import router as scrape_router
from app.config import get_settings

settings = get_settings()

# ── Structured logging ───────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)
structlog.configure(
    wrapper_class=structlog.make_filtering_bound_logger(
        getattr(logging, settings.log_level.upper(), logging.INFO)
    )
)

# ── App ──────────────────────────────────────────────────────────────
app = FastAPI(
    title="Spotify Review RAG API",
    description=(
        "Scrape Spotify reviews from Google Play, App Store, and Reddit, "
        "then ask natural-language questions answered via RAG."
    ),
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────
app.include_router(scrape_router)
app.include_router(reviews_router)
app.include_router(query_router)


@app.get("/health", tags=["health"])
async def health_check():
    return {"status": "ok", "env": settings.app_env}
