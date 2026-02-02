"""Main cache service with business logic."""

import asyncio
import logging
from datetime import datetime
from typing import Dict

from config.settings import Settings
from schema.cache import CacheMetadata
from repository.github_repository import GitHubRepository
from repository.base_repository import CacheRepository

logger = logging.getLogger(__name__)


class CacheService:
    """Service for managing file caching logic."""

    def __init__(
        self,
        settings: Settings,
        cache_repo: CacheRepository,
        github_repo: GitHubRepository,
    ) -> None:
        """Initialize cache service."""
        self.settings = settings
        self.cache_repo = cache_repo
        self.github_repo = github_repo
        # Lock dictionary to prevent concurrent downloads of the same file
        self._download_locks: Dict[str, asyncio.Lock] = {}

    def _is_whitelisted(self, owner: str, repo: str) -> bool:
        """Check if repository is whitelisted."""
        if not self.settings.repositories:
            return True

        target = f"{owner}/{repo}".lower()
        for whitelisted in self.settings.repositories:
            whitelisted_normalized = whitelisted.lower()
            # If whitelist entry is a URL, it might contain the target owner/repo
            # If whitelist entry is just owner or owner/repo, it might be part of the target
            if whitelisted_normalized in target or target in whitelisted_normalized:
                return True
        return False

    async def get_cached_file(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> tuple[bytes, str] | None:
        """
        Get cached file content and content type.

        Returns None if file is not cached or cache is invalid.
        """
        if not self._is_whitelisted(owner, repo):
            raise PermissionError(f"Repository {owner}/{repo} is not whitelisted")

        # Check repository for metadata
        metadata = await self.cache_repo.get_metadata(owner, repo, path, ref)
        if not metadata:
            logger.info(
                f"Cache MISS: no metadata in Redis for {owner}/{repo}/{path}@{ref}"
            )
            return None

        logger.info(f"Cache metadata found in Redis for {owner}/{repo}/{path}@{ref}")

        # Get file content from repository
        content = await self.cache_repo.get_content(owner, repo, path, ref)
        if not content:
            # File content not in cache, clean up stale metadata
            logger.info(
                f"Cache MISS: file content not in cache, cleaning up metadata for {owner}/{repo}/{path}@{ref}"
            )
            await self.cache_repo.delete_metadata(owner, repo, path, ref)
            return None

        # Cache hit
        logger.info(
            f"Cache HIT: serving {owner}/{repo}/{path}@{ref} (size: {len(content)} bytes)"
        )
        return content, metadata.content_type

    async def cache_file(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> tuple[bytes, str]:
        """
        Download file from GitHub, cache it in Redis, and return content and content type.

        Raises exception if file cannot be fetched from GitHub.
        """
        # Get file info from GitHub
        file_info = await self.github_repo.get_file_info(owner, repo, path, ref)
        if not file_info:
            raise FileNotFoundError(f"File not found: {owner}/{repo}/{path}@{ref}")

        # Download file content
        content = await self.github_repo.download_file(file_info.download_url)

        # Store content in repository
        await self.cache_repo.set_content(owner, repo, path, ref, content)

        # Store metadata in repository
        metadata = CacheMetadata(
            sha=file_info.sha,
            content_type=file_info.content_type,
            cached_at=datetime.utcnow(),
            size=file_info.size,
        )
        await self.cache_repo.set_metadata(owner, repo, path, ref, metadata)

        return content, file_info.content_type

    def _get_lock_key(self, owner: str, repo: str, path: str, ref: str) -> str:
        """Generate lock key for preventing concurrent downloads."""
        return f"{owner}:{repo}:{path}:{ref}"

    async def get_metadata(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> CacheMetadata | None:
        """Get cache metadata for a file."""
        return await self.cache_repo.get_metadata(owner, repo, path, ref)

    async def invalidate_cache(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> None:
        """Invalidate cache for a specific file."""
        await self.cache_repo.delete_metadata(owner, repo, path, ref)
        await self.cache_repo.delete_content(owner, repo, path, ref)

    async def get_or_cache_file(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> tuple[bytes, str]:
        """
        Get file from cache or download and cache it.

        Returns (content, content_type).
        Uses locking to prevent concurrent downloads of the same file.
        """
        # Try to get from cache first
        cached = await self.get_cached_file(owner, repo, path, ref)
        if cached:
            content, content_type = cached
            return content, content_type

        # Not in cache - acquire lock to prevent concurrent downloads
        lock_key = self._get_lock_key(owner, repo, path, ref)
        if lock_key not in self._download_locks:
            self._download_locks[lock_key] = asyncio.Lock()

        async with self._download_locks[lock_key]:
            # Check cache again after acquiring lock (another request might have cached it)
            cached = await self.get_cached_file(owner, repo, path, ref)
            if cached:
                logger.info(
                    f"Cache HIT after lock: {owner}/{repo}/{path}@{ref} was cached by concurrent request"
                )
                content, content_type = cached
                return content, content_type

            # Still not in cache, fetch and cache
            logger.info(f"Fetching and caching {owner}/{repo}/{path}@{ref} from GitHub")
            content, content_type = await self.cache_file(owner, repo, path, ref)
            logger.info(
                f"Cached {owner}/{repo}/{path}@{ref} for {self.settings.cache_ttl_seconds}s"
            )
            return content, content_type
