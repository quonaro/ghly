import logging
from litestar import Controller, get
from litestar.exceptions import HTTPException
from litestar.response import Response
from litestar.status_codes import HTTP_200_OK, HTTP_404_NOT_FOUND

from service.cache_service import CacheService

logger = logging.getLogger(__name__)


class ProxyController(Controller):
    """Controller for handling GitHub file proxy requests."""

    path = "/gh"

    @get("/{owner:str}/{repo:str}/{path:str}")
    async def proxy_file(
        self,
        owner: str,
        repo: str,
        path: str,
        cache_service: CacheService,
        ref: str = "main",
        refresh: bool = False,
    ) -> Response:
        """
        Proxy GitHub file request.

        Args:
            owner: Repository owner
            repo: Repository name
            path: File path in repository
            ref: Branch, tag, or commit hash (default: main)
            refresh: Force cache refresh (default: False)

        Returns:
            File content with appropriate headers
        """
        try:
            # Force cache refresh if requested
            if refresh:
                await cache_service.invalidate_cache(owner, repo, path, ref)

            content, content_type = await cache_service.get_or_cache_file(
                owner=owner,
                repo=repo,
                path=path,
                ref=ref,
            )

            # Get metadata for ETag
            metadata = await cache_service.get_metadata(owner, repo, path, ref)
            etag = f'"{metadata.sha[:16]}"' if metadata else None

            headers = {
                "Cache-Control": "public, max-age=3600, must-revalidate",
                "X-Cache-Status": "HIT",
            }

            if etag:
                headers["ETag"] = etag

            return Response(
                content=content,
                media_type=content_type,
                status_code=HTTP_200_OK,
                headers=headers,
            )
        except FileNotFoundError:
            raise HTTPException(
                status_code=HTTP_404_NOT_FOUND,
                detail=f"File not found: {owner}/{repo}/{path}@{ref}",
            )
        except PermissionError as e:
            # Rely on application-level permission error handler
            raise e
        except HTTPException as e:
            # Re-raise HTTP exceptions (like 404 from GitHub)
            raise e
        except Exception as e:
            logger.exception(f"Unexpected error in proxy_file: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Internal server error: {str(e)}",
            )
