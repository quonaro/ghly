"""Cache-related data schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class CacheMetadata(BaseModel):
    """Metadata stored in Redis for cached files."""

    sha: str = Field(..., description="Git SHA/hash of the file")
    content_type: str = Field(..., description="MIME type of the file")
    cached_at: datetime = Field(..., description="When the file was cached")
    size: int = Field(..., description="File size in bytes")

    class Config:
        """Pydantic config."""

        json_encoders = {
            datetime: lambda v: v.isoformat(),
        }


class FileInfo(BaseModel):
    """Information about a file from GitHub."""

    sha: str
    content_type: str
    download_url: str
    size: int
    path: str

