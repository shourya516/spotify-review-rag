# High-Level Architecture: Spotify Review RAG System

## Overview

A full-stack AI application that scrapes Spotify user reviews from multiple platforms, stores and indexes them, and uses Retrieval-Augmented Generation (RAG) to answer natural-language product questions grounded in real user feedback.

---

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                          USER (Browser)                              │
└──────────────────────────────┬──────────────────────────────────────┘
                               │ HTTPS
                               ▼
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (Next.js)                            │
│                                                                      │
│   ┌─────────────────┐   ┌──────────────────┐   ┌─────────────────┐ │
│   │  Scrape Trigger │   │  Ingestion Status │   │   Q&A Interface │ │
│   │     Panel       │   │     Dashboard     │   │  + Citations    │ │
│   └────────┬────────┘   └────────┬─────────┘   └────────┬────────┘ │
└────────────┼────────────────────┼──────────────────────┼───────────┘
             │                    │                       │
             │         REST API / HTTP (JSON)             │
             ▼                    ▼                       ▼
┌─────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                            │
│                                                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     API Layer                                │   │
│  │  POST /scrape   GET /status   POST /query   GET /reviews     │   │
│  └──────────────┬───────────────────────────────┬──────────────┘   │
│                 │                               │                   │
│  ┌──────────────▼──────────────┐  ┌────────────▼──────────────┐   │
│  │      Scraping Service        │  │       RAG Pipeline         │   │
│  │                              │  │                            │   │
│  │  ┌──────────┐ ┌──────────┐  │  │  ┌──────────────────────┐ │   │
│  │  │ Play     │ │ App      │  │  │  │  Query Embedding      │ │   │
│  │  │ Store    │ │ Store    │  │  │  │  (Embedding Model)    │ │   │
│  │  │ Scraper  │ │ Scraper  │  │  │  └──────────┬───────────┘ │   │
│  │  └──────────┘ └──────────┘  │  │             │             │   │
│  │  ┌──────────┐               │  │  ┌──────────▼───────────┐ │   │
│  │  │ Reddit   │               │  │  │  Vector Retrieval     │ │   │
│  │  │ Scraper  │               │  │  │  (Top-K Similarity)   │ │   │
│  │  └──────────┘               │  │  └──────────┬───────────┘ │   │
│  └──────────────┬──────────────┘  │             │             │   │
│                 │                 │  ┌──────────▼───────────┐ │   │
│  ┌──────────────▼──────────────┐  │  │  LLM Generation      │ │   │
│  │    Data Cleaning Service     │  │  │  (with context +     │ │   │
│  │  (dedup, spam, HTML, URLs)   │  │  │   citations)         │ │   │
│  └──────────────┬──────────────┘  │  └──────────────────────┘ │   │
│                 │                 └────────────────────────────┘   │
│  ┌──────────────▼──────────────┐                                   │
│  │   Embedding Service          │                                   │
│  │  (generate + store vectors)  │                                   │
│  └──────────────┬──────────────┘                                   │
└─────────────────┼───────────────────────────────────────────────────┘
                  │
       ┌──────────┴────────────┐
       ▼                       ▼
┌──────────────┐      ┌─────────────────────┐
│  PostgreSQL  │      │   Vector Store       │
│  (Reviews +  │      │  (pgvector extension │
│   Metadata)  │      │   or Pinecone/Qdrant)│
└──────────────┘      └─────────────────────┘
```

---

## Component Breakdown

### 1. Frontend — Next.js

| Component | Responsibility |
|-----------|---------------|
| Scrape Trigger Panel | Initiates review collection from selected sources |
| Ingestion Status Dashboard | Polls backend for scraping progress and review counts |
| Q&A Interface | Accepts natural-language queries, displays AI answers |
| Citations Panel | Renders source reviews used as evidence for each answer |

**Key design choices:**
- Server-side rendering (SSR) for initial load performance
- React Query or SWR for polling ingestion status
- Tailwind CSS for UI styling

---

### 2. Backend — FastAPI

#### API Layer
| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/scrape` | POST | Trigger scraping job for one or all sources |
| `/scrape/status` | GET | Return current ingestion progress |
| `/reviews` | GET | List stored reviews with filters |
| `/query` | POST | Accept a question, return RAG-generated answer + citations |

#### Scraping Service
- **Google Play Store Scraper** — `google-play-scraper` library
- **Apple App Store Scraper** — `app-store-scraper` or iTunes RSS feed
- **Reddit Scraper** — PRAW (Python Reddit API Wrapper), targeting r/spotify and related subreddits
- Jobs run asynchronously (Celery + Redis, or FastAPI BackgroundTasks)

#### Data Cleaning Service
- Remove HTML tags, URLs, emojis (configurable)
- Deduplicate by content hash
- Filter spam/bot reviews by length and pattern heuristics
- Normalize text (lowercase, whitespace)

#### Embedding Service
- Generates vector embeddings per review using a sentence transformer model (e.g., `text-embedding-3-small` via OpenAI, or `all-MiniLM-L6-v2` via HuggingFace)
- Stores vectors alongside review records

#### RAG Pipeline
1. **Embed the query** using the same model as reviews
2. **Retrieve top-K reviews** via cosine similarity search in the vector store
3. **Construct prompt** with retrieved reviews as context
4. **Generate answer** via an LLM (e.g., GPT-4o or Claude)
5. **Return response** with answer text + cited review IDs/snippets

---

### 3. Data Layer

#### PostgreSQL
Stores structured review data:

```
reviews
-------
id              UUID PK
source          ENUM (play_store, app_store, reddit)
author          TEXT
rating          INT (nullable for Reddit)
content         TEXT
cleaned_content TEXT
review_date     TIMESTAMP
scraped_at      TIMESTAMP
content_hash    TEXT UNIQUE  ← for deduplication
embedding_id    TEXT         ← reference to vector store entry
```

#### Vector Store
Two options depending on scale:
- **pgvector** (PostgreSQL extension) — keeps everything in one DB, simpler ops
- **Qdrant / Pinecone** — dedicated vector DB, better performance at scale

Stores: `(review_id, embedding_vector, metadata)`

---

## Data Flow

### Ingestion Flow
```
Scraper → Raw Reviews → Cleaning Service → PostgreSQL
                                        → Embedding Service → Vector Store
```

### Query Flow
```
User Query
    → Embed Query
    → Vector Similarity Search → Top-K Review Chunks
    → LLM Prompt Construction (query + retrieved reviews)
    → LLM Response
    → Return Answer + Citations to Frontend
```

---

## Technology Stack Summary

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js, React, Tailwind CSS |
| Backend API | FastAPI (Python) |
| Scraping | google-play-scraper, PRAW, iTunes RSS |
| Task Queue | Celery + Redis (or FastAPI BackgroundTasks) |
| Database | PostgreSQL |
| Vector Store | pgvector (or Qdrant/Pinecone) |
| Embeddings | OpenAI `text-embedding-3-small` or `all-MiniLM-L6-v2` |
| LLM | OpenAI GPT-4o (or Anthropic Claude) |
| Deployment | Docker Compose (dev) → Railway / Render / AWS ECS (prod) |

---

## Deployment Architecture

```
┌─────────────────────────────────────────┐
│              Docker Compose              │
│                                          │
│  ┌──────────┐  ┌──────────┐  ┌────────┐ │
│  │ next.js  │  │ fastapi  │  │ redis  │ │
│  │ :3000    │  │ :8000    │  │ :6379  │ │
│  └──────────┘  └──────────┘  └────────┘ │
│  ┌──────────────────────────────────┐   │
│  │     postgresql + pgvector        │   │
│  │           :5432                  │   │
│  └──────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

For production, each service maps to an independent container/service on the chosen cloud provider, with the PostgreSQL instance managed separately (e.g., RDS, Supabase, or Neon).

---

## Key Design Decisions

1. **pgvector over a separate vector DB** — Reduces operational complexity by keeping embeddings and review text in the same database. Can migrate to Qdrant/Pinecone if query latency becomes a bottleneck.

2. **Async scraping jobs** — Scraping is slow and rate-limited; running it as background tasks prevents blocking the API and lets the frontend poll for status.

3. **Content hash deduplication** — Reviews scraped from overlapping sources (e.g., a Reddit post linking a Play Store review) are deduplicated before storage.

4. **Citation-grounded responses** — The RAG prompt explicitly instructs the LLM to only use provided review context, with each answer returning the source review IDs for frontend rendering.

5. **Source metadata preserved** — Each review retains its `source` field, enabling cross-source comparisons (e.g., "Play Store vs Reddit sentiment").
