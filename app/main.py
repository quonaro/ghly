"""Main Litestar application."""

from contextlib import asynccontextmanager

from litestar import Litestar
from litestar.di import Provide

from config.settings import get_settings
from controller.proxy_controller import ProxyController
from repository.github_repository import GitHubRepository
from repository.redis_repository import RedisRepository
from service.cache_service import CacheService

# Global instances for lifecycle management
_redis_repo: RedisRepository | None = None
_github_repo: GitHubRepository | None = None


async def get_redis_repository() -> RedisRepository:
    """Dependency: Get Redis repository instance."""
    global _redis_repo
    if _redis_repo is None:
        settings = get_settings()
        _redis_repo = RedisRepository(settings)
        await _redis_repo.connect()
    return _redis_repo


async def get_github_repository() -> GitHubRepository:
    """Dependency: Get GitHub repository instance."""
    global _github_repo
    if _github_repo is None:
        settings = get_settings()
        _github_repo = GitHubRepository(settings)
    return _github_repo


async def get_cache_service(
    redis_repo: RedisRepository,
    github_repo: GitHubRepository,
) -> CacheService:
    """Dependency: Get cache service instance."""
    settings = get_settings()
    return CacheService(settings, redis_repo, github_repo)


@asynccontextmanager
async def lifespan(app: Litestar):
    """Application lifespan context manager."""
    # Startup
    settings = get_settings()
    global _redis_repo, _github_repo

    _redis_repo = RedisRepository(settings)
    await _redis_repo.connect()

    _github_repo = GitHubRepository(settings)

    yield

    # Shutdown
    if _redis_repo:
        await _redis_repo.disconnect()
    if _github_repo:
        await _github_repo.close()


def create_app() -> Litestar:
    """Create and configure Litestar application."""
    return Litestar(
        route_handlers=[ProxyController],
        dependencies={
            "redis_repo": Provide(get_redis_repository),
            "github_repo": Provide(get_github_repository),
            "cache_service": Provide(get_cache_service),
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
        host=settings.server_host,
        reload=True,
        port=settings.server_port,
        workers=24,
    )
