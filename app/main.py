"""Main Litestar application."""

from contextlib import asynccontextmanager

from litestar import Litestar, Request, Response
from litestar.di import Provide
from litestar.exceptions import NotFoundException
from litestar.status_codes import HTTP_400_BAD_REQUEST

from config.settings import get_settings
from controller.proxy_controller import ProxyController
from repository.github_repository import GitHubRepository
from repository.base_repository import CacheRepository
from repository.redis_repository import RedisRepository
from repository.file_repository import FileRepository
from service.cache_service import CacheService

# Global instances for lifecycle management
_cache_repo: CacheRepository | None = None
_github_repo: GitHubRepository | None = None


async def get_cache_repository() -> CacheRepository:
    """Dependency: Get cache repository instance (Redis or File)."""
    global _cache_repo
    if _cache_repo is None:
        settings = get_settings()
        if settings.use_redis:
            _cache_repo = RedisRepository(settings)
            await _cache_repo.connect()
        else:
            _cache_repo = FileRepository(settings)
    return _cache_repo


async def get_github_repository() -> GitHubRepository:
    """Dependency: Get GitHub repository instance."""
    global _github_repo
    if _github_repo is None:
        settings = get_settings()
        _github_repo = GitHubRepository(settings)
    return _github_repo


async def get_cache_service(
    cache_repo: CacheRepository,
    github_repo: GitHubRepository,
) -> CacheService:
    """Dependency: Get cache service instance."""
    settings = get_settings()
    return CacheService(settings, cache_repo, github_repo)


def not_found_handler(request: Request, exc: NotFoundException) -> Response:
    """Handle 404 errors with custom guidance for /gh paths."""
    if request.url.path.startswith("/gh"):
        return Response(
            content={
                "status_code": HTTP_400_BAD_REQUEST,
                "detail": "Invalid API path format. Correct template: /gh/{owner}/{repo}/{path}?ref={branch}",
            },
            status_code=HTTP_400_BAD_REQUEST,
        )
    return Response(
        content={
            "status_code": exc.status_code,
            "detail": exc.detail,
        },
        status_code=exc.status_code,
    )


def permission_error_handler(request: Request, exc: PermissionError) -> Response:
    """Handle PermissionError (whitelist violations)."""
    import logging

    logger = logging.getLogger("ghly.main")
    logger.error(f"Permission denied for {request.url.path}: {exc}")
    return Response(
        content={
            "status_code": 403,
            "detail": str(exc),
        },
        status_code=403,
    )


@asynccontextmanager
async def lifespan(app: Litestar):
    """Application lifespan context manager."""
    # Startup
    settings = get_settings()
    global _cache_repo, _github_repo

    if settings.use_redis:
        _cache_repo = RedisRepository(settings)
        await _cache_repo.connect()
    else:
        _cache_repo = FileRepository(settings)

    _github_repo = GitHubRepository(settings)

    yield

    # Shutdown
    if _cache_repo:
        await _cache_repo.disconnect()
    if _github_repo:
        await _github_repo.close()


def create_app() -> Litestar:
    """Create and configure Litestar application."""
    settings = get_settings()
    return Litestar(
        debug=settings.dev,
        route_handlers=[ProxyController],
        dependencies={
            "cache_repo": Provide(get_cache_repository),
            "github_repo": Provide(get_github_repository),
            "cache_service": Provide(get_cache_service),
        },
        exception_handlers={
            NotFoundException: not_found_handler,
            PermissionError: permission_error_handler,
        },
        lifespan=[lifespan],
    )


app = create_app()


if __name__ == "__main__":
    import sys
    import uvicorn
    from pathlib import Path

    # Add app directory to path for imports
    app_dir = Path(__file__).parent
    if str(app_dir) not in sys.path:
        sys.path.insert(0, str(app_dir))

    settings = get_settings()

    uvicorn.run(
        "main:app",
        reload=settings.dev,
        host=settings.server_host,
        port=settings.server_port,
        workers=settings.workers,
        log_level="info",
    )
