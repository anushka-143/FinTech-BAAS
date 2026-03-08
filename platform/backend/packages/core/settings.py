"""Application settings loaded from environment via Pydantic Settings."""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ─── Database ───
    database_url: str = (
        "postgresql+asyncpg://fintech:fintech_secret@localhost:5432/fintech_platform"
    )
    database_pool_size: int = 20
    database_max_overflow: int = 10
    # Read replica for AI queries — empty = falls back to primary
    database_readonly_url: str = ""

    # ─── Redis ───
    redis_url: str = "redis://localhost:6379/0"

    # ─── Auth / Security ───
    jwt_secret_key: str = "CHANGE_ME_IN_PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 30
    jwt_refresh_token_expire_minutes: int = 10080
    hmac_secret_key: str = "CHANGE_ME_IN_PRODUCTION"

    # ─── Redpanda / Kafka ───
    redpanda_bootstrap_servers: str = "localhost:19092"

    # ─── Temporal ───
    temporal_host: str = "localhost:7233"
    temporal_namespace: str = "fintech-platform"

    # ─── Google Gemini / Vertex AI ───
    google_api_key: str = ""  # Direct Gemini API (fallback)
    gemini_model_name: str = "gemini-2.5-pro"
    google_application_credentials: str = ""  # Path to service account JSON
    gcp_project_id: str = ""  # Vertex AI project
    gcp_location: str = "us-central1"  # Vertex AI region

    # ─── Object Storage ───
    s3_endpoint_url: str = "http://localhost:9000"
    s3_access_key_id: str = "minioadmin"
    s3_secret_access_key: str = "minioadmin"
    s3_bucket_documents: str = "fintech-documents"

    # ─── Banking Partner (our own bank connections) ───
    bank_partner_id: str = "sandbox"
    bank_partner_api_key: str = "sandbox-key"
    bank_partner_api_secret: str = "sandbox-secret"
    bank_partner_base_url: str = "http://localhost:8001"

    # ─── Observability ───
    otel_exporter_otlp_endpoint: str = "http://localhost:4317"

    # ─── App ───
    environment: str = "development"
    log_level: str = "DEBUG"
    cors_origins: str = "http://localhost:3000,http://localhost:8080,http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",")]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
