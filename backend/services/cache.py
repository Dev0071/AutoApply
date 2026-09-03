from __future__ import annotations
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

    async def close(self) -> None:
        """Release the connection pool. Without this, a worker running under
        asyncio.run() raises 'Event loop is closed' from the finalizer."""
        closer = getattr(self._redis, "aclose", None) or getattr(self._redis, "close", None)
        if closer is not None:
            await closer()

    async def incr(self, key: str, ttl: int = 86_400) -> int:
        """Atomically increment a counter, setting its TTL on first increment.
        Used for per-user, per-platform daily rate limiting."""
        count = await self._redis.incr(key)
        if count == 1:
            await self._redis.expire(key, ttl)
        return count
