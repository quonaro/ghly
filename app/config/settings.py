"""Application settings using Pydantic Settings."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # GitHub configuration
    github_token: str | None = None  # Not needed when using raw.githubusercontent.com
    github_api_url: str = "https://api.github.com"  # Not used anymore
    github_raw_url: str = "https://raw.githubusercontent.com"

    # Redis configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None
    redis_url: str | None = None  # If set, overrides host/port/db/password

    # Cache configuration
    cache_ttl_seconds: int = 300  # 5 minutes default (can be reduced to 60-120 seconds)

    # Server configuration
    server_host: str = "0.0.0.0"
    server_port: int = 8000

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()

