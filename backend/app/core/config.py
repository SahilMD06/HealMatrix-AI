"""Application configuration.

All settings are sourced from environment variables (or a local ``.env`` file) so the
same image can run unchanged in development, staging and production. No environment
specific branching is permitted anywhere else in the codebase.
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Typed, validated application settings."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ------------------------------------------------------------------ core
    app_name: str = "HealMatrix AI"
    app_version: str = "1.0.0"
    environment: Literal["development", "staging", "production", "test"] = "development"
    api_v1_prefix: str = "/api/v1"
    debug: bool = False

    # ------------------------------------------------------------------ cors
    backend_cors_origins: str = "http://localhost:5173"

    # -------------------------------------------------------------- database
    mongodb_uri: str = "mongodb://localhost:27017"
    mongodb_db_name: str = "healmatrix"
    mongodb_max_pool_size: int = 50
    mongodb_min_pool_size: int = 5

    # -------------------------------------------------------------- security
    jwt_secret_key: str = Field(
        default="insecure-development-key-change-me-immediately-0123456789",
        min_length=32,
    )
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60
    refresh_token_expire_days: int = 7
    bcrypt_rounds: int = 12
    auth_rate_limit: str = "10/minute"

    # ----------------------------------------------------------- redis/celery
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"
    cache_ttl_seconds: int = 60

    # ---------------------------------------------------------------- gemini
    google_api_key: str = ""
    gemini_model: str = "gemini-2.0-flash"
    gemini_temperature: float = 0.2
    gemini_max_output_tokens: int = 2048
    gemini_timeout_seconds: int = 30

    # ------------------------------------------------------------ cloudinary
    cloudinary_cloud_name: str = ""
    cloudinary_api_key: str = ""
    cloudinary_api_secret: str = ""

    # ------------------------------------------------------------------- rag
    embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2"
    faiss_index_path: str = "app/rag/index"
    knowledge_base_path: str = "../knowledge_base"
    rag_top_k: int = 5
    rag_score_threshold: float = 0.35
    rag_chunk_size: int = 800
    rag_chunk_overlap: int = 120

    # ------------------------------------------------------------- simulator
    simulator_enabled: bool = True
    simulator_tick_seconds: int = 30
    simulator_seed: int = 42

    # --------------------------------------------------------------- routing
    osrm_base_url: str = "https://router.project-osrm.org"
    routing_detour_factor: float = 1.35

    # --------------------------------------------------------------- agents
    agent_timeout_seconds: int = 30
    agent_max_retries: int = 2
    executive_cycle_timeout_seconds: int = 45

    # ------------------------------------------------------------ validators
    @field_validator("jwt_secret_key")
    @classmethod
    def _reject_default_secret_in_production(cls, value: str, info) -> str:
        env = (info.data or {}).get("environment")
        if env == "production" and value.startswith("insecure-development-key"):
            raise ValueError("JWT_SECRET_KEY must be set to a real secret in production")
        return value

    # ------------------------------------------------------------ properties
    @property
    def cors_origins(self) -> list[str]:
        """CORS origins as a list, parsed from the comma separated env value."""
        return [origin.strip() for origin in self.backend_cors_origins.split(",") if origin.strip()]

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @property
    def llm_available(self) -> bool:
        """Whether agents may attempt an LLM call, or must go straight to fallback."""
        return bool(self.google_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton."""
    return Settings()


settings = get_settings()
