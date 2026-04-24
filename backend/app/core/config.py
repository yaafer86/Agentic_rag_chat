from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Auth & app
    jwt_secret: str = Field(default="change-me")
    app_base_url: str = Field(default="http://localhost:3000")
    api_base_url: str = Field(default="http://localhost:8000")

    # Databases
    postgres_url: str = Field(default="postgresql+asyncpg://rag:rag@localhost:5432/rag_db")
    qdrant_url: str = Field(default="http://localhost:6333")
    neo4j_uri: str = Field(default="bolt://localhost:7687")
    neo4j_user: str = Field(default="neo4j")
    neo4j_password: str = Field(default="changeme")

    # Storage
    minio_endpoint: str = Field(default="localhost:9000")
    minio_access_key: str = Field(default="minioadmin")
    minio_secret_key: str = Field(default="minioadmin")
    minio_bucket: str = Field(default="rag-files")
    minio_secure: bool = Field(default=False)

    # LLM routing
    openai_api_key: str | None = None
    anthropic_api_key: str | None = None
    openrouter_api_key: str | None = None
    ollama_base_url: str = Field(default="http://localhost:11434")
    lmstudio_url: str = Field(default="http://localhost:1234")
    litellm_default_timeout: int = Field(default=30)
    litellm_max_retries: int = Field(default=2)

    # Sandbox
    sandbox_image: str = Field(default="python:3.11-slim")
    sandbox_timeout: int = Field(default=30)
    sandbox_max_memory_mb: int = Field(default=512)
    sandbox_network_enabled: bool = Field(default=False)

    # Extraction & validation
    vlm_temperature: float = Field(default=0.2)
    ocr_fallback_threshold: float = Field(default=0.65)
    max_context_tokens: int = Field(default=8192)
    enable_semantic_cache: bool = Field(default=True)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
