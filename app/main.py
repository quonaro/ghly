"""Main Litestar application."""

import sys
import uvicorn
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from litestar import Litestar, Request, Response
from litestar.di import Provide
from litestar.datastructures import State
from litestar.exceptions import NotFoundException


from config.settings import get_settings
from controller.proxy_controller import ProxyController
from repository.github_repository import GitHubRepository
from repository.base_repository import CacheRepository
from repository.redis_repository import RedisRepository
from repository.file_repository import FileRepository
from service.cache_service import CacheService


async def get_cache_repository(state: State) -> CacheRepository:
    """Dependency: Get cache repository instance from app state."""
    return state.cache_repo


async def get_github_repository(state: State) -> GitHubRepository:
    """Dependency: Get GitHub repository instance from app state."""
    return state.github_repo


async def get_cache_service(
    cache_repo: CacheRepository,
    github_repo: GitHubRepository,
) -> CacheService:
    """Dependency: Get cache service instance."""
    settings = get_settings()
    return CacheService(settings, cache_repo, github_repo)


def not_found_handler(request: Request, exc: NotFoundException) -> Response:
    """Handle 404 errors with custom guidance for /gh paths."""
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
    """Application lifespan context manager for initializing resources."""
    settings = get_settings()

    # Initialize repositories
    logger = logging.getLogger("ghly.main")
    if settings.use_redis:
        repo_target = (
            settings.redis_url or f"{settings.redis_host}:{settings.redis_port}"
        )
        logger.info(f"Using Redis cache at {repo_target}")
        cache_repo = RedisRepository(settings)
        await cache_repo.connect()
    else:
        logger.info(f"Using SQLite cache at {settings.cache_file_path}")
        cache_repo = FileRepository(settings)

    github_repo = GitHubRepository(settings)

    # Store in app state
    app.state.cache_repo = cache_repo
    app.state.github_repo = github_repo

    yield

    # Cleanup
    if hasattr(app.state, "cache_repo"):
        await app.state.cache_repo.disconnect()

    if hasattr(app.state, "github_repo"):
        await app.state.github_repo.close()


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
