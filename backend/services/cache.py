import redis.asyncio as aioredis
import structlog

from backend.config import settings

log = structlog.get_logger()


class CacheService:
    def __init__(self):
        self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)

    async def get(self, key: str) -> str | None:
        return await self._redis.get(key)

    async def set(self, key: str, value: str, ttl: int = 3600) -> None:
        await self._redis.set(key, value, ex=ttl)

    async def delete(self, key: str) -> None:
        await self._redis.delete(key)
