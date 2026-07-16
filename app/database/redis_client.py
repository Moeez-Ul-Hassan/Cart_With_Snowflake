import redis
from app.core.config import settings
import structlog

logger = structlog.get_logger()

redis_pool = redis.ConnectionPool.from_url(settings.REDIS_URL, decode_responses=True)

def get_redis():
    """Dependency to inject Redis client into services."""
    client = redis.Redis(connection_pool=redis_pool)
    try:
        client.ping()
        yield client
    except redis.ConnectionError as e:
        logger.error("redis_connection_failed", error=str(e))
        raise