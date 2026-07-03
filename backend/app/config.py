from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql+asyncpg://postgres:password@localhost:5432/spotify_reviews"
    sync_database_url: str = "postgresql+psycopg2://postgres:password@localhost:5432/spotify_reviews"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # OpenAI
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_llm_model: str = "gpt-4o"

    # Reddit
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "SpotifyReviewScraper/1.0"

    # App
    app_env: str = "development"
    log_level: str = "INFO"

    # RAG
    rag_top_k: int = 10
    rag_min_similarity: float = 0.70


@lru_cache
def get_settings() -> Settings:
    return Settings()
