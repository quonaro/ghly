"""Redis repository for cache metadata and file content."""

import base64
import json
from datetime import datetime
from typing import Optional

from redis.asyncio import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
from pydantic import ValidationError

from config.settings import Settings
from repository.base_repository import CacheRepository
from schema.cache import CacheMetadata


class RedisRepository(CacheRepository):
    """Repository for managing cache metadata in Redis."""

    def __init__(self, settings: Settings) -> None:
        """Initialize Redis repository."""
        self.settings = settings
        self._client: Optional[Redis] = None

    async def connect(self) -> None:
        """Connect to Redis."""
        # Close existing client if it exists to prevent connection leaks
        if self._client:
            try:
                await self._client.aclose()
            except Exception:
                pass
            self._client = None

        if self.settings.redis_url:
            self._client = Redis.from_url(
                self.settings.redis_url,
                decode_responses=True,
            )
        else:
            if self.settings.redis_password:
                redis_url = f"redis://:{self.settings.redis_password}@{self.settings.redis_host}:{self.settings.redis_port}/{self.settings.redis_db}"
            else:
                redis_url = f"redis://{self.settings.redis_host}:{self.settings.redis_port}/{self.settings.redis_db}"
            self._client = Redis.from_url(
                redis_url,
                decode_responses=True,
            )

        # Test connection
        try:
            await self._client.ping()
        except Exception:
            self._client = None
            raise

    async def disconnect(self) -> None:
        """Disconnect from Redis."""
        if self._client:
            await self._client.aclose()
            self._client = None

    def _make_key(self, owner: str, repo: str, path: str, ref: str) -> str:
        """Generate cache key from components."""
        return f"gh:{owner}:{repo}@{ref}:{path}"

    def _make_content_key(self, owner: str, repo: str, path: str, ref: str) -> str:
        """Generate cache key for file content."""
        return f"gh:content:{owner}:{repo}@{ref}:{path}"

    async def get_metadata(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> Optional[CacheMetadata]:
        """Get cache metadata for a file."""
        if not self._client:
            await self.connect()

        key = self._make_key(owner, repo, path, ref)
        try:
            data = await self._client.get(key)
        except (RedisConnectionError, OSError):
            await self.connect()
            data = await self._client.get(key)

        if not data:
            return None

        try:
            metadata_dict = json.loads(data)
            # Convert cached_at string back to datetime
            if isinstance(metadata_dict.get("cached_at"), str):
                metadata_dict["cached_at"] = datetime.fromisoformat(
                    metadata_dict["cached_at"]
                )
            return CacheMetadata(**metadata_dict)
        except (json.JSONDecodeError, ValidationError, ValueError):
            return None

    async def set_metadata(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
        metadata: CacheMetadata,
    ) -> None:
        """Store cache metadata for a file."""
        if not self._client:
            await self.connect()

        key = self._make_key(owner, repo, path, ref)
        data = metadata.model_dump_json()

        try:
            await self._client.setex(
                key,
                self.settings.cache_ttl_seconds,
                data,
            )
        except (RedisConnectionError, OSError):
            await self.connect()
            await self._client.setex(
                key,
                self.settings.cache_ttl_seconds,
                data,
            )

    async def delete_metadata(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> None:
        """Delete cache metadata and content from Redis."""
        if not self._client:
            await self.connect()

        key = self._make_key(owner, repo, path, ref)
        content_key = self._make_content_key(owner, repo, path, ref)
        # Delete both metadata and content
        try:
            await self._client.delete(key, content_key)
        except (RedisConnectionError, OSError):
            await self.connect()
            await self._client.delete(key, content_key)

    async def exists(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> bool:
        """Check if cache metadata exists."""
        if not self._client:
            await self.connect()

        key = self._make_key(owner, repo, path, ref)
        try:
            return await self._client.exists(key) > 0
        except (RedisConnectionError, OSError):
            await self.connect()
            return await self._client.exists(key) > 0

    async def get_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> Optional[bytes]:
        """Get cached file content from Redis."""
        if not self._client:
            await self.connect()

        key = self._make_content_key(owner, repo, path, ref)
        # Redis client uses decode_responses=True, so we store content as base64 string
        try:
            data = await self._client.get(key)
        except (RedisConnectionError, OSError):
            await self.connect()
            data = await self._client.get(key)
        if not data:
            return None
        return base64.b64decode(data)

    async def set_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
        content: bytes,
    ) -> None:
        """Store file content in Redis as base64 string."""
        if not self._client:
            await self.connect()

        key = self._make_content_key(owner, repo, path, ref)
        # Redis client uses decode_responses=True, so encode content as base64 string
        encoded = base64.b64encode(content).decode("utf-8")
        try:
            await self._client.setex(key, self.settings.cache_ttl_seconds, encoded)
        except (RedisConnectionError, OSError):
            await self.connect()
            await self._client.setex(key, self.settings.cache_ttl_seconds, encoded)

    async def delete_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> None:
        """Delete cached file content from Redis."""
        if not self._client:
            await self.connect()

        key = self._make_content_key(owner, repo, path, ref)
        try:
            await self._client.delete(key)
        except (RedisConnectionError, OSError):
            await self.connect()
            await self._client.delete(key)
