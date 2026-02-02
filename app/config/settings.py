"""Application settings using Pydantic Settings."""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    github_raw_url: str = "https://raw.githubusercontent.com"

    # Redis configuration
    redis_host: str = "localhost"
    redis_port: int = 6379
    redis_db: int = 0
    redis_password: str | None = None
    redis_url: str | None = None  # If set, overrides host/port/db/password

    # Cache configuration
    cache_ttl_seconds: int = 300  # 5 minutes default
    cache_file_path: str = "ghly.cache"

    # Whitelist configuration
    repositories: list[str] = []  # List of repository URLs or owner/repo strings

    @field_validator("repositories", mode="before")
    @classmethod
    def parse_repositories(cls, v):
        if isinstance(v, str):
            if not v.strip():
                return []
            return [item.strip() for item in v.split(",")]
        return v

    # Server configuration
    server_host: str = "0.0.0.0"
    server_port: int = 8000
    dev: bool = True
    workers: int = 1

    @property
    def use_redis(self) -> bool:
        """Check if Redis should be used for caching."""
        return bool(self.redis_url or (self.redis_host and self.redis_port))

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


def get_settings() -> Settings:
    """Get application settings instance."""
    return Settings()
