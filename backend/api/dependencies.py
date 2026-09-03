from __future__ import annotations

import anthropic
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import settings
from backend.db.session import AsyncSessionLocal


async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session


async def get_anthropic() -> anthropic.AsyncAnthropic:
    from backend.services.anthropic_client import build_anthropic_client

    return build_anthropic_client()


async def get_cache():
    """Redis client for JD dedupe. Cache reads/writes are best-effort in the
    miner, so a Redis outage degrades to re-mining rather than failing."""
    from backend.services.cache import CacheService

    return CacheService()
