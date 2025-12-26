"""GitHub raw content repository for fetching files directly."""

import hashlib
import mimetypes
from typing import Optional

import httpx

from config.settings import Settings
from schema.cache import FileInfo


class GitHubRepository:
    """Repository for fetching files from raw.githubusercontent.com."""

    def __init__(self, settings: Settings) -> None:
        """Initialize GitHub repository."""
        self.settings = settings
        self.client = httpx.AsyncClient(
            base_url=self.settings.github_raw_url,
            timeout=30.0,
            follow_redirects=True,
        )

    async def close(self) -> None:
        """Close HTTP client."""
        await self.client.aclose()

    def _build_raw_url(self, owner: str, repo: str, path: str, ref: str) -> str:
        """Build raw.githubusercontent.com URL for file."""
        # Normalize path (remove leading slash, handle refs/heads/ prefix)
        clean_path = path.lstrip("/")
        clean_ref = ref
        if clean_ref.startswith("refs/heads/"):
            clean_ref = clean_ref.replace("refs/heads/", "")
        elif clean_ref.startswith("refs/tags/"):
            clean_ref = clean_ref.replace("refs/tags/", "")

        return f"/{owner}/{repo}/{clean_ref}/{clean_path}"

    def _detect_content_type(
        self, path: str, content: bytes, response_headers: dict
    ) -> str:
        """Detect content type from path, content, and response headers."""
        # Try Content-Type header first
        content_type = response_headers.get("content-type", "")
        if content_type and not content_type.startswith("text/plain"):
            # Remove charset if present
            content_type = content_type.split(";")[0].strip()
            if content_type:
                return content_type

        # Try mimetypes
        content_type, _ = mimetypes.guess_type(path)
        if content_type:
            return content_type

        # Fallback to common types
        if path.endswith((".js", ".mjs")):
            return "application/javascript"
        if path.endswith(".css"):
            return "text/css"
        if path.endswith((".json",)):
            return "application/json"
        if path.endswith((".html", ".htm")):
            return "text/html"
        if path.endswith((".svg",)):
            return "image/svg+xml"
        if path.endswith((".txt",)):
            return "text/plain"
        if path.endswith((".md", ".markdown")):
            return "text/markdown"

        return "application/octet-stream"

    async def get_file_info(
        self,
        owner: str,
        repo: str,
        path: str,
        ref: str,
    ) -> Optional[FileInfo]:
        """
        Get file info by downloading from raw.githubusercontent.com.

        Since we don't have API access, we generate a SHA from file content
        and use ETag if available for change detection.
        """
        try:
            url = self._build_raw_url(owner, repo, path, ref)
            response = await self.client.get(url)
            response.raise_for_status()

            content = response.content
            size = len(content)

            # Generate SHA from content (not actual git SHA, but good enough for change detection)
            sha = hashlib.sha256(content).hexdigest()

            # Use ETag if available, otherwise use content hash
            etag = response.headers.get("etag", "").strip('"')
            if etag:
                sha = etag

            content_type = self._detect_content_type(path, content, response.headers)

            download_url = f"{self.settings.github_raw_url}{url}"

            return FileInfo(
                sha=sha,
                content_type=content_type,
                download_url=download_url,
                size=size,
                path=path,
            )
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                return None
            raise
        except httpx.RequestError:
            raise

    async def download_file(self, download_url: str) -> bytes:
        """
        Download file content from raw.githubusercontent.com.

        Can accept full URL or relative path.
        """
        # If it's a full URL, extract the path
        if download_url.startswith(self.settings.github_raw_url):
            url = download_url[len(self.settings.github_raw_url) :]
        elif download_url.startswith("http://") or download_url.startswith("https://"):
            # External URL, use directly
            async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
                response = await client.get(download_url)
                response.raise_for_status()
                return response.content
        else:
            # Assume it's already a relative path
            url = download_url

        response = await self.client.get(url)
        response.raise_for_status()
        return response.content
