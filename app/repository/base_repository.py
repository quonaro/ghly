"""Base interface for cache repositories."""

from typing import Protocol, Optional, runtime_checkable
from schema.cache import CacheMetadata


@runtime_checkable
class CacheRepository(Protocol):
    """Protocol for cache repository implementations."""

    async def get_metadata(
        self, owner: str, repo: str, path: str, ref: str
    ) -> Optional[CacheMetadata]: ...

    async def set_metadata(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
        metadata: CacheMetadata,
        ttl: Optional[int] = None,
    ) -> None: ...

    async def delete_metadata(
        self, owner: str, repo: str, path: str, ref: str
    ) -> None: ...

    async def get_content(
        self, owner: str, repo: str, path: str, ref: str
    ) -> Optional[bytes]: ...

    async def set_content(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
        content: bytes,
        ttl: Optional[int] = None,
    ) -> None: ...

    async def delete_content(
        self, owner: str, repo: str, path: str, ref: str
    ) -> None: ...

    async def disconnect(self) -> None: ...
