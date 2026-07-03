# Spotify Review RAG — Backend

FastAPI backend for the Spotify Review RAG system.

## Quick Start

### 1. Prerequisites
- Docker + Docker Compose
- An OpenAI API key
- Reddit API credentials (create an app at https://www.reddit.com/prefs/apps)

### 2. Configure environment

```bash
cp .env.example .env
# Fill in OPENAI_API_KEY, REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET
```

### 3. Start all services

```bash
# From the project root (RAG/)
docker-compose up --build
```

This starts:
- PostgreSQL 16 + pgvector on port 5432
- Redis on port 6379
- FastAPI on port 8000 (auto-reload enabled)
- Celery worker (2 concurrent tasks)

### 4. Run database migrations

```bash
docker-compose exec api alembic upgrade head
```

### 5. Open the API docs

http://localhost:8000/docs

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/scrape` | Trigger review scraping (async) |
| `GET`  | `/scrape/{id}` | Poll job status |
| `GET`  | `/scrape` | List recent jobs |
| `GET`  | `/reviews` | List reviews with filters |
| `POST` | `/query` | Ask a question via RAG |
| `GET`  | `/health` | Health check |

### Example: trigger a scrape

```bash
curl -X POST http://localhost:8000/scrape \
  -H "Content-Type: application/json" \
  -d '{"source": "play_store", "count": 200}'
```

### Example: ask a question

```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"question": "What are the most common complaints about Spotify recommendations?"}'
```

---

## Project Structure

```
backend/
├── app/
│   ├── api/           # FastAPI routers
│   │   ├── scrape.py  # POST/GET /scrape
│   │   ├── reviews.py # GET /reviews
│   │   └── query.py   # POST /query
│   ├── db/
│   │   ├── models.py  # SQLAlchemy ORM models
│   │   └── session.py # Async + sync engines
│   ├── schemas/       # Pydantic request/response models
│   ├── services/
│   │   ├── scraper.py # Play Store, App Store, Reddit scrapers
│   │   ├── cleaner.py # HTML stripping, dedup, spam filter
│   │   ├── embedder.py# OpenAI embedding generation
│   │   └── rag.py     # Retrieval + LLM generation pipeline
│   ├── worker/
│   │   ├── celery_app.py # Celery configuration
│   │   └── tasks.py      # Scrape + embed task
│   ├── config.py      # Pydantic settings
│   └── main.py        # FastAPI app + middleware
├── alembic/           # DB migrations
├── Dockerfile
├── requirements.txt
└── .env.example
```

---

## Local Development (without Docker)

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt

# Start Redis and PostgreSQL separately, then:
alembic upgrade head
uvicorn app.main:app --reload

# In a separate terminal, start the worker:
celery -A app.worker.celery_app worker --loglevel=info
```
