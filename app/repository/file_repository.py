"""SQLite repository for file-based caching."""

import json
import sqlite3
import logging
from datetime import datetime
from typing import Optional

from config.settings import Settings
from schema.cache import CacheMetadata
from repository.base_repository import CacheRepository

logger = logging.getLogger(__name__)


class FileRepository(CacheRepository):
    """SQLite-based repository for caching when Redis is unavailable."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.db_path = settings.cache_file_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize SQLite database."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS cache (
                    key TEXT PRIMARY KEY,
                    metadata TEXT,
                    content BLOB,
                    expires_at TIMESTAMP
                )
                """
            )
            # Cleanup expired entries on startup
            conn.execute("DELETE FROM cache WHERE expires_at < ?", (datetime.utcnow(),))
            conn.commit()

    def _make_key(self, owner: str, repo: str, path: str, ref: str) -> str:
        return f"{owner}:{repo}@{ref}:{path}"

    async def get_metadata(
        self, owner: str, repo: str, path: str, ref: str
    ) -> Optional[CacheMetadata]:
        key = self._make_key(owner, repo, path, ref)
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT metadata FROM cache WHERE key = ? AND expires_at > ?",
                    (key, datetime.utcnow()),
                ).fetchone()

                if not row:
                    return None

                data = json.loads(row[0])
                if isinstance(data.get("cached_at"), str):
                    data["cached_at"] = datetime.fromisoformat(data["cached_at"])
                return CacheMetadata(**data)
        except Exception as e:
            logger.error(f"Error reading metadata from SQLite: {e}")
            return None

    async def set_metadata(
        self, owner: str, repo: str, path: str, ref: str, metadata: CacheMetadata
    ) -> None:
        key = self._make_key(owner, repo, path, ref)
        expires_at = datetime.utcnow().timestamp() + self.settings.cache_ttl_seconds
        expires_at_dt = datetime.fromtimestamp(expires_at)

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    """
                    INSERT INTO cache (key, metadata, expires_at)
                    VALUES (?, ?, ?)
                    ON CONFLICT(key) DO UPDATE SET
                        metadata = excluded.metadata,
                        expires_at = excluded.expires_at
                    """,
                    (key, metadata.model_dump_json(), expires_at_dt),
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error writing metadata to SQLite: {e}")

    async def delete_metadata(self, owner: str, repo: str, path: str, ref: str) -> None:
        key = self._make_key(owner, repo, path, ref)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("DELETE FROM cache WHERE key = ?", (key,))
            conn.commit()

    async def get_content(
        self, owner: str, repo: str, path: str, ref: str
    ) -> Optional[bytes]:
        key = self._make_key(owner, repo, path, ref)
        try:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT content FROM cache WHERE key = ? AND expires_at > ?",
                    (key, datetime.utcnow()),
                ).fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.error(f"Error reading content from SQLite: {e}")
            return None

    async def set_content(
        self, owner: str, repo: str, path: str, ref: str, content: bytes
    ) -> None:
        key = self._make_key(owner, repo, path, ref)
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute(
                    "UPDATE cache SET content = ? WHERE key = ?", (content, key)
                )
                conn.commit()
        except Exception as e:
            logger.error(f"Error writing content to SQLite: {e}")

    async def delete_content(self, owner: str, repo: str, path: str, ref: str) -> None:
        # Combined with delete_metadata in SQLite for simplicity if needed,
        # but here we follow the interface.
        pass

    async def disconnect(self) -> None:
        pass
