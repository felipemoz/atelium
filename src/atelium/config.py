from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="ATELIUM_",
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_debug: bool = False
    auth_disabled: bool = False

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_step_ttl_seconds: int = 86400  # 24h

    # PostgreSQL
    postgres_dsn: str = "postgresql+asyncpg://atelium:atelium@localhost:5432/atelium"

    # NATS
    nats_url: str = "nats://localhost:4222"

    # Ollama
    ollama_url: str = "http://localhost:11434"
    embed_model: str = "nomic-embed-text"
    embed_dim: int = 768

    # Routing weights
    routing_alpha: float = 0.50
    routing_beta: float = 0.30
    routing_gamma: float = 0.10
    routing_delta: float = 0.10
    routing_lambda: float = 0.10
    routing_min_affinity: float = 0.40
    routing_candidate_pool: int = 50

    # Circuit breaker
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_timeout_ms: int = 60_000

    # HITL
    hitl_timeout_ms: int = 3_600_000  # 1h

    # Observability
    langfuse_host: str = "http://localhost:3000"
    langfuse_url: str = "http://localhost:3000"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    otel_endpoint: str = "http://localhost:4317"
    otel_enabled: bool = False


settings = Settings()
